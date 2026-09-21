"""Migration runner for versioned database schema changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Protocol

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
