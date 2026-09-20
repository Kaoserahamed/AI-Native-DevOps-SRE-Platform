"""Database models and session management for the demo API.

The demo API uses a single ``items`` table to store demo records. The model is
defined with SQLAlchemy 2.0's declarative mapping and exposed through an async
session factory that is initialised at application startup.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Final

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

logger = logging.getLogger("demo-api.database")

# Consistent naming convention for auto-generated constraints.
NAMING_CONVENTION: Final[dict[str, str]] = {
    "ix": "ix_%(table_name)s_%(column_names)s",
    "uq": "uq_%(table_name)s_%(column_names)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_names)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all demo API models."""

    metadata = metadata


class Item(Base):
    """A simple demo record with a name and optional description."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False, comment="Short display name.")
    description: Mapped[str | None] = mapped_column(default=None, comment="Optional detail.")
    is_active: Mapped[bool] = mapped_column(default=True, comment="Whether the item is active.")
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When the item was created.",
    )

    def __repr__(self) -> str:
        return f"Item(id={self.id!r}, name={self.name!r})"


def create_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine from a connection string."""
    logger.info("Creating database engine")
    return create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to ``engine``."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def check_database_health(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    """Return ``True`` when the database accepts connections."""
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False
