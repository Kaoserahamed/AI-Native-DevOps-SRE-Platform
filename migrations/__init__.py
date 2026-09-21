"""Database migration framework.

Provides versioned schema migrations for PostgreSQL using SQLAlchemy Core.
Migrations are applied sequentially and tracked in a migrations table.
"""

from __future__ import annotations

__all__ = ["Migration", "MigrationRunner"]

from migrations.runner import Migration, MigrationRunner
