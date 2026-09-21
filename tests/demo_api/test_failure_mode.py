"""Tests for the controllable failure mode that the incident scenario injects.

The demo API ships one intentional fault behind a development-only flag so that the platform's detection and
diagnosis paths can be exercised deterministically. Asserting its behaviour is an ordinary unit concern: the
test drives the real application stack over an in-memory database and an in-process Redis double, with no
external service and no waiting.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tests.demo_api.conftest import FakeRedis

from services.demo_api.app import create_app
from services.demo_api.config import AppEnvironment, FailureMode, Settings
from services.demo_api.db.models import Base
from services.demo_api.db.session import set_session_factory
from services.demo_api.redis_client import set_redis_client

pytestmark = pytest.mark.unit


@pytest_asyncio.fixture
async def failing_app() -> AsyncIterator[AsyncClient]:
    """Build a test app with a 100% error-rate failure mode."""
    settings = Settings(
        app_env=AppEnvironment.DEVELOPMENT,
        database_url="sqlite+aiosqlite:///:memory:",  # type: ignore[arg-type]
        redis_url="redis://localhost:6379/0",  # type: ignore[arg-type]
        failure_mode=FailureMode.ERROR_RATE,
        failure_rate=1.0,
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

    set_redis_client(FakeRedis())

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await engine.dispose()


async def test_failure_mode_returns_503(failing_app: AsyncClient) -> None:
    """With failure_rate=1.0, requests return 503."""
    response = await failing_app.get("/items/")
    assert response.status_code == 503
    assert "failure_mode" in response.json()["detail"]
