"""Tests for database migrations."""

from __future__ import annotations

from datetime import UTC, datetime

from migrations.runner import MigrationRunner
from migrations.versions import initial_schema as migration_001
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@pytest.fixture
async def test_engine() -> AsyncEngine:
    """Create in-memory SQLite engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    yield engine
    await engine.dispose()


class TestMigrationRunner:
    """Test migration runner."""

    @pytest.mark.asyncio
    async def test_creates_migrations_table(self, test_engine: AsyncEngine) -> None:
        """Test that runner creates schema_migrations table."""
        runner = MigrationRunner(test_engine, [])

        async with test_engine.begin() as conn:
            await runner.ensure_migrations_table(conn)

            # Verify table exists
            result = await conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
                )
            )
            assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_tracks_applied_migrations(self, test_engine: AsyncEngine) -> None:
        """Test that applied migrations are tracked."""
        runner = MigrationRunner(test_engine, [migration_001])

        applied = await runner.run_migrations()

        assert len(applied) == 1
        assert applied[0].version == 1
        assert applied[0].description == migration_001.description

        # Verify tracking record
        version = await runner.get_schema_version()
        assert version == 1

    @pytest.mark.asyncio
    async def test_skips_already_applied_migrations(self, test_engine: AsyncEngine) -> None:
        """Test that already-applied migrations are skipped."""
        runner = MigrationRunner(test_engine, [migration_001])

        # Run once
        await runner.run_migrations()

        # Run again
        applied = await runner.run_migrations()

        assert len(applied) == 0  # Nothing new applied

    @pytest.mark.asyncio
    async def test_runs_migrations_in_order(self, test_engine: AsyncEngine) -> None:
        """Test that migrations run in version order."""
        # Create multiple migrations (only migration_001 exists for now)
        runner = MigrationRunner(test_engine, [migration_001])

        applied = await runner.run_migrations()

        versions = [m.version for m in applied]
        assert versions == sorted(versions)


class TestInitialSchemaMigration:
    """Test initial schema migration."""

    @pytest.mark.asyncio
    async def test_creates_incidents_table(self, test_engine: AsyncEngine) -> None:
        """Test that migration creates incidents table."""
        runner = MigrationRunner(test_engine, [migration_001])
        await runner.run_migrations()

        async with test_engine.connect() as conn:
            # Check table exists
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='incidents'")
            )
            assert result.fetchone() is not None

            # Check columns exist
            result = await conn.execute(text("PRAGMA table_info(incidents)"))
            columns = {row[1] for row in result.fetchall()}

            expected_columns = {
                "id",
                "incident_id",
                "title",
                "severity",
                "status",
                "service_name",
                "service_environment",
                "detected_at",
                "opened_at",
            }
            assert expected_columns.issubset(columns)

    @pytest.mark.asyncio
    async def test_creates_evidence_table(self, test_engine: AsyncEngine) -> None:
        """Test that migration creates evidence table."""
        runner = MigrationRunner(test_engine, [migration_001])
        await runner.run_migrations()

        async with test_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='evidence'")
            )
            assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_creates_remediation_tables(self, test_engine: AsyncEngine) -> None:
        """Test that migration creates remediation tables."""
        runner = MigrationRunner(test_engine, [migration_001])
        await runner.run_migrations()

        async with test_engine.connect() as conn:
            # Check proposals table
            result = await conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='remediation_proposals'"
                )
            )
            assert result.fetchone() is not None

            # Check approvals table
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='approvals'")
            )
            assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_creates_agent_executions_table(self, test_engine: AsyncEngine) -> None:
        """Test that migration creates agent executions table."""
        runner = MigrationRunner(test_engine, [migration_001])
        await runner.run_migrations()

        async with test_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_executions'"
                )
            )
            assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_creates_audit_log_table(self, test_engine: AsyncEngine) -> None:
        """Test that migration creates audit log table."""
        runner = MigrationRunner(test_engine, [migration_001])
        await runner.run_migrations()

        async with test_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
            )
            assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_creates_idempotency_keys_table(self, test_engine: AsyncEngine) -> None:
        """Test that migration creates idempotency keys table."""
        runner = MigrationRunner(test_engine, [migration_001])
        await runner.run_migrations()

        async with test_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='idempotency_keys'"
                )
            )
            assert result.fetchone() is not None

    @pytest.mark.asyncio
    async def test_creates_indexes(self, test_engine: AsyncEngine) -> None:
        """Test that migration creates indexes."""
        runner = MigrationRunner(test_engine, [migration_001])
        await runner.run_migrations()

        async with test_engine.connect() as conn:
            # Check for indexes on incidents table
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='incidents'")
            )
            indexes = {row[0] for row in result.fetchall()}

            # Should have indexes on incident_id, status, service_name, etc.
            assert any("incident_id" in idx.lower() for idx in indexes)

    @pytest.mark.asyncio
    async def test_incidents_can_be_inserted(self, test_engine: AsyncEngine) -> None:
        """Test that incidents can be inserted after migration."""
        runner = MigrationRunner(test_engine, [migration_001])
        await runner.run_migrations()

        async with test_engine.connect() as conn:
            result = await conn.execute(
                text("""
                    INSERT INTO incidents (
                        incident_id, title, severity, status,
                        service_name, service_environment,
                        detected_at, opened_at, created_at, updated_at
                    ) VALUES (
                        :incident_id, :title, :severity, :status,
                        :service_name, :service_environment,
                        :detected_at, :opened_at, :created_at, :updated_at
                    )
                """),
                {
                    "incident_id": "INC-001",
                    "title": "Test incident",
                    "severity": "sev2",
                    "status": "open",
                    "service_name": "demo-api",
                    "service_environment": "production",
                    "detected_at": datetime.now(tz=UTC),
                    "opened_at": datetime.now(tz=UTC),
                    "created_at": datetime.now(tz=UTC),
                    "updated_at": datetime.now(tz=UTC),
                },
            )
            await conn.commit()

            # Verify insert
            result = await conn.execute(
                text("SELECT incident_id FROM incidents WHERE incident_id = 'INC-001'")
            )
            assert result.fetchone() is not None


class TestMigrationIdempotency:
    """Test migration idempotency."""

    @pytest.mark.asyncio
    async def test_migration_is_idempotent(self, test_engine: AsyncEngine) -> None:
        """Test that running migrations multiple times is safe."""
        runner = MigrationRunner(test_engine, [migration_001])

        # Run migrations twice
        await runner.run_migrations()
        applied = await runner.run_migrations()

        # Second run should apply nothing
        assert len(applied) == 0

        # Schema should still be valid
        async with test_engine.connect() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM schema_migrations"))
            count = result.scalar()
            assert count == 1
