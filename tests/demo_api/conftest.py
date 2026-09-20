"""Shared fixtures for demo API tests.

Tests run against an in-memory SQLite database and a fake in-memory Redis so
no external service is required. Lifespan-driven startup is bypassed: the
session factory and Redis client are injected directly, and the app is served
through httpx's ``ASGITransport``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from services.demo_api.app import create_app
from services.demo_api.config import AppEnvironment, Settings
from services.demo_api.db.models import Base, Item
from services.demo_api.db.session import set_session_factory
from services.demo_api.redis_client import set_redis_client


class FakeRedis:
    """Minimal async Redis double backed by a dict."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                removed += 1
        return removed

    async def aclose(self) -> None:
        return None


@pytest_asyncio.fixture
async def app_client() -> AsyncIterator[AsyncClient]:
    """Yield an ``AsyncClient`` bound to a fully wired test app."""
    settings = Settings(
        app_env=AppEnvironment.DEVELOPMENT,
        database_url="sqlite+aiosqlite:///:memory:",  # type: ignore[arg-type]
        redis_url="redis://localhost:6379/0",  # type: ignore[arg-type]
        enable_tracing=False,
    )

    engine = create_async_engine(
        str(settings.database_url),
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    set_session_factory(session_factory)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(Item(name="seeded-item", description="Seeded for contract tests"))
        await session.commit()

    fake_redis = FakeRedis()
    set_redis_client(fake_redis)

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await engine.dispose()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# Backwards-compatible aliases so existing test modules keep working.
@pytest_asyncio.fixture
async def async_client(app_client: AsyncClient) -> AsyncClient:
    return app_client


@pytest_asyncio.fixture
async def sync_client(app_client: AsyncClient) -> AsyncClient:
    return app_client
