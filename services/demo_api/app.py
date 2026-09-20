"""FastAPI application factory for the demo API service.

The factory pattern keeps the app creation side-effect-free and testable:
tests can construct an app with overridden dependencies without touching the
real database, Redis or OpenTelemetry backend.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.demo_api.config import Settings
from services.demo_api.db.models import Base, create_engine, create_session_factory
from services.demo_api.db.session import set_session_factory
from services.demo_api.logging import configure_logging
from services.demo_api.middleware.correlation import CorrelationIdMiddleware
from services.demo_api.observability.metrics import setup_metrics
from services.demo_api.observability.tracing import init_tracing, shutdown_tracing
from services.demo_api.redis_client import set_redis_client
from services.demo_api.routes.health import router as health_router
from services.demo_api.routes.items import router as items_router
from services.demo_api.routes.metrics import router as metrics_router
from services.demo_api.version import __version__

logger = logging.getLogger("demo-api.app")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construct and configure the FastAPI application.

    Parameters
    ----------
    settings
        Optional pre-built settings. When ``None``, settings are loaded from
        the environment / ``.env`` file.
    """
    settings = settings if settings is not None else Settings()  # type: ignore[call-arg]
    configure_logging(settings.log_level_value, "demo-api", __version__, settings.app_env.value)
    setup_metrics("demo-api", __version__, settings.app_env.value)

    @asynccontextmanager
    async def lifespan(
        app: FastAPI,
    ) -> AsyncIterator[None]:
        # --- Startup ---
        logger.info("Starting demo-api v%s in %s mode", __version__, settings.app_env.value)

        # Database
        engine = create_engine(str(settings.database_url))
        session_factory = create_session_factory(engine)
        set_session_factory(session_factory)

        # Create tables (idempotent; in production migrations would handle this)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database connection established and tables verified")

        # Redis
        import redis.asyncio as redis_client_module

        redis_client = redis_client_module.from_url(  # type: ignore[no-untyped-call]
            str(settings.redis_url), decode_responses=False
        )
        set_redis_client(redis_client)
        logger.info("Redis connection established")

        # Tracing
        provider = init_tracing(
            "demo-api",
            __version__,
            settings.app_env.value,
            str(settings.otel_endpoint) if settings.otel_endpoint else None,
            settings.enable_tracing,
        )

        app.state.tracing_provider = provider

        yield

        # --- Shutdown ---
        logger.info("Shutting down demo-api")
        await redis_client.aclose()
        await engine.dispose()
        shutdown_tracing(provider)
        logger.info("Demo-api shutdown complete")

    app = FastAPI(
        title="Demo API",
        description="Observable data-plane workload for the AI-Native DevOps/SRE platform.",
        version=__version__,
        lifespan=lifespan,
    )

    # Make settings accessible in route handlers and middleware
    app.state.settings = settings

    # Middleware
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.add_middleware(CorrelationIdMiddleware)

    # Routes
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(items_router)

    return app
