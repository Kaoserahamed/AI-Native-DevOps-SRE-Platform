"""Migration runner for versioned database schema changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import importlib.util
import logging
from pathlib import Path
from typing import Final, Protocol, cast

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

logger = logging.getLogger(__name__)


class Migration(Protocol):
    """Protocol for a database migration."""

    version: int
    description: str

    async def up(self, conn: AsyncConnection, metadata: MetaData) -> None:
        """Apply the migration."""
        ...

    async def down(self, conn: AsyncConnection, metadata: MetaData) -> None:
        """Rollback the migration (optional, for down migrations)."""
        ...


@dataclass
class MigrationRecord:
    """Record of an applied migration."""

    version: int
    description: str
    applied_at: datetime


#: Directory holding the versioned migration modules. They are loaded by path because a migration file is
#: named after the schema version it introduces (`001_initial_schema.py`), which is not a valid Python
#: identifier: importing it by module name would need a rename that hides the version it carries.
VERSIONS_DIR: Final[Path] = Path(__file__).resolve().parent / "versions"


def load_migrations(directory: Path | None = None) -> list[Migration]:
    """Load every migration module in ``directory`` (default: ``migrations/versions``).

    Returns
    -------
    list[Migration]
        The migrations, ordered by version. A file that does not define both ``version`` and ``up`` is
        skipped rather than failing the whole load, so an in-progress migration cannot break startup.
    """
    resolved = directory or VERSIONS_DIR
    migrations: list[Migration] = []
    if not resolved.is_dir():
        return migrations

    for path in sorted(resolved.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"migrations.versions.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:  # pragma: no cover
            raise RuntimeError(f"unable to load migration module {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        version = getattr(module, "version", None)
        up = getattr(module, "up", None)
        if not isinstance(version, int) or not callable(up):
            logger.warning("Skipping %s: no version/up pair declared", path.name)
            continue
        migrations.append(cast(Migration, module))

    return sorted(migrations, key=lambda migration: migration.version)


class MigrationRunner:
    """Runs database migrations in sequence."""

    def __init__(self, engine: AsyncEngine, migrations: list[Migration]) -> None:
        """Initialize migration runner.

        Parameters
        ----------
        engine
            Database engine
        migrations
            List of migrations to run, ordered by version
        """
        self.engine = engine
        self.migrations = sorted(migrations, key=lambda m: m.version)
        self.metadata = MetaData()

        # Migrations tracking table
        self.schema_migrations = Table(
            "schema_migrations",
            self.metadata,
            Column("version", Integer, primary_key=True),
            Column("description", String(255), nullable=False),
            Column("applied_at", DateTime(timezone=True), nullable=False),
        )

    async def ensure_migrations_table(self, conn: AsyncConnection) -> None:
        """Create migrations tracking table if it doesn't exist."""
        await conn.run_sync(self.schema_migrations.create, checkfirst=True)

    async def get_applied_versions(self, conn: AsyncConnection) -> set[int]:
        """Get set of applied migration versions."""
        result = await conn.execute(select(self.schema_migrations.c.version))
        return {row[0] for row in result.fetchall()}

    async def record_migration(self, conn: AsyncConnection, version: int, description: str) -> None:
        """Record a successful migration."""
        await conn.execute(
            insert(self.schema_migrations).values(
                version=version,
                description=description,
                applied_at=datetime.now(tz=UTC),
            )
        )

    async def run_migrations(self) -> list[MigrationRecord]:
        """Run all pending migrations.

        Returns
        -------
        list[MigrationRecord]
            Migrations that were applied
        """
        applied: list[MigrationRecord] = []

        async with self.engine.begin() as conn:
            await self.ensure_migrations_table(conn)
            existing = await self.get_applied_versions(conn)

            for migration in self.migrations:
                if migration.version in existing:
                    logger.debug("Migration %d already applied, skipping", migration.version)
                    continue

                logger.info("Applying migration %d: %s", migration.version, migration.description)

                await migration.up(conn, self.metadata)
                await self.record_migration(conn, migration.version, migration.description)

                applied.append(
                    MigrationRecord(
                        version=migration.version,
                        description=migration.description,
                        applied_at=datetime.now(tz=UTC),
                    )
                )

                logger.info("Migration %d applied successfully", migration.version)

        return applied

    async def get_schema_version(self) -> int:
        """Get current schema version (highest applied migration)."""
        async with self.engine.connect() as conn:
            await self.ensure_migrations_table(conn)
            versions = await self.get_applied_versions(conn)
            return max(versions) if versions else 0
