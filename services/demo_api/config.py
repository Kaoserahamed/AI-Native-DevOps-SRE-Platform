"""Configuration model and validation for the demo API service.

All configuration is sourced from environment variables (with optional
``.env`` file support) so the same image runs identically in every environment.
The ``failure_mode`` flag is restricted to development and test environments so
that failure-injection can never be enabled in production.
"""

from __future__ import annotations

from enum import StrEnum
from functools import cached_property
import logging
from typing import Self

from pydantic import AnyUrl, Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.demo_api.version import __version__


class AppEnvironment(StrEnum):
    """Deployment environments the demo API can run in."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class FailureMode(StrEnum):
    """Controllable failure modes for testing (development/test only)."""

    ERROR_RATE = "error_rate"
    DATABASE_TIMEOUT = "database_timeout"
    REDIS_FAILURE = "redis_failure"


class Settings(BaseSettings):
    """Runtime configuration sourced from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        case_sensitive=False,
    )

    # --- Application identity ---
    app_name: str = "demo-api"
    app_env: AppEnvironment = Field(
        default=AppEnvironment.DEVELOPMENT, description="Deployment environment."
    )
    app_version: str = Field(default=__version__, description="Semantic version of the service.")

    # --- Server ---
    host: str = Field(default="0.0.0.0", description="Bind address for the ASGI server.")
    port: int = Field(default=8000, ge=1, le=65535, description="Listen port.")
    log_level: str = Field(default="INFO", description="Python logging level name.")
    reload: bool = Field(default=False, description="Enable auto-reload (development only).")

    # --- Data stores ---
    # ``AnyUrl`` (not ``PostgresDsn``) so tests can inject an in-memory SQLite
    # URL; production deployments still require PostgreSQL (see validator).
    database_url: AnyUrl = Field(description="Database connection string.")
    redis_url: AnyUrl = Field(description="Redis connection string.")

    # --- Observability ---
    otel_endpoint: HttpUrl | None = Field(
        default=None, description="OTLP gRPC collector endpoint (e.g. http://otel-collector:4317)."
    )
    enable_metrics: bool = Field(default=True, description="Expose Prometheus metrics endpoint.")
    enable_tracing: bool = Field(default=True, description="Initialise OpenTelemetry tracing.")

    # --- Test-only failure injection ---
    failure_mode: FailureMode | None = Field(
        default=None,
        description=(
            "Controllable failure mode for testing. Only permitted in development; "
            "the model validator below enforces this in production."
        ),
    )
    failure_rate: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Probability that a request triggers the failure."
    )

    @property
    def log_level_value(self) -> int:
        """Return the numeric logging level for ``log_level``."""
        return logging.getLevelNamesMapping().get(self.log_level.upper(), logging.INFO)

    @cached_property
    def is_production(self) -> bool:
        """Return whether this configuration targets production."""
        return self.app_env is AppEnvironment.PRODUCTION

    @model_validator(mode="before")
    @classmethod
    def normalize_blank_optional_settings(cls, values: object) -> object:
        """Treat a blank value for an optional setting as "not set".

        ConfigMaps, `.env` files and chart values routinely carry empty strings for keys that are simply
        not configured in that environment. Rejecting them would turn a harmless empty value into a
        crash-looping pod, so a blank ``otel_endpoint`` or ``failure_mode`` is normalised to "unset" here,
        while a blank value for a *required* setting still fails validation.
        """
        if not isinstance(values, dict):
            return values

        normalized = dict(values)
        for field in ("otel_endpoint", "failure_mode"):
            for key, value in list(normalized.items()):
                if key.lower() != field:
                    continue
                if isinstance(value, str) and value.strip() == "":
                    normalized[key] = None
        return normalized

    @model_validator(mode="after")
    def validate_database_url(self) -> Self:
        """Production must use PostgreSQL; SQLite is test-only."""
        scheme = self.database_url.scheme or ""
        if self.app_env is AppEnvironment.PRODUCTION and not scheme.startswith("postgres"):
            raise ValueError("database_url must use a PostgreSQL scheme in production.")
        return self

    @model_validator(mode="after")
    def validate_failure_mode(self) -> Self:
        """Reject failure injection outside development environments."""
        if self.failure_mode is not None and self.app_env is not AppEnvironment.DEVELOPMENT:
            raise ValueError(
                "failure_mode is only permitted in the development environment; "
                "never enable failure injection in production or staging."
            )
        return self

    @model_validator(mode="after")
    def validate_reload(self) -> Self:
        """Auto-reload is a development-only feature."""
        if self.reload and self.app_env is not AppEnvironment.DEVELOPMENT:
            raise ValueError("reload is only permitted in the development environment.")
        return self
