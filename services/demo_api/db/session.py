"""Async database session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# The session factory is set at startup; routes depend on this module-level
# reference so FastAPI dependency overrides work cleanly in tests.
_session_factory: async_sessionmaker[AsyncSession] | None = None


def set_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Inject the session factory created at application startup."""
    global _session_factory
    _session_factory = factory


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the active session factory."""
    if _session_factory is None:
        raise RuntimeError("Database session factory has not been initialised")
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
