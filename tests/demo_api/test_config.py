"""Unit tests for the demo API configuration model."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
import pytest

from services.demo_api.config import AppEnvironment, FailureMode, Settings

pytestmark = pytest.mark.unit

_TEST_DB_URL: Any = "postgresql+asyncpg://user:pass@host:5432/db"
_TEST_REDIS_URL: Any = "redis://localhost:6379/0"


def test_default_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings validate successfully when required fields are provided."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    settings = Settings()  # type: ignore[call-arg]
    assert settings.app_env is AppEnvironment.DEVELOPMENT
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000


def test_failure_mode_rejected_in_production() -> None:
    """failure_mode must never be set in a production environment."""
    with pytest.raises(ValidationError):
        Settings(
            database_url=_TEST_DB_URL,
            redis_url=_TEST_REDIS_URL,
            app_env=AppEnvironment.PRODUCTION,
            failure_mode=FailureMode.ERROR_RATE,
        )


def test_reload_rejected_outside_development() -> None:
    """Auto-reload is a development-only flag."""
    with pytest.raises(ValidationError):
        Settings(
            database_url=_TEST_DB_URL,
            redis_url=_TEST_REDIS_URL,
            app_env=AppEnvironment.STAGING,
            reload=True,
        )


def test_failure_rate_bounds() -> None:
    """failure_rate must be between 0 and 1."""
    with pytest.raises(ValidationError):
        Settings(
            database_url=_TEST_DB_URL,
            redis_url=_TEST_REDIS_URL,
            failure_rate=1.5,
        )


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_optional_settings_are_treated_as_unset(blank: str) -> None:
    """A blank optional value means "not configured", not "invalid".

    Kubernetes ConfigMaps routinely carry an empty string for a key that an environment does not
    configure. Rejecting that would crash-loop a pod over a value that means nothing is enabled.
    """
    settings = Settings(
        database_url=_TEST_DB_URL,
        redis_url=_TEST_REDIS_URL,
        otel_endpoint=blank,  # type: ignore[arg-type]
        failure_mode=blank,  # type: ignore[arg-type]
    )

    assert settings.otel_endpoint is None
    assert settings.failure_mode is None


def test_blank_optional_settings_from_the_environment_are_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same normalisation applies to values injected as environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OTEL_ENDPOINT", "")
    monkeypatch.setenv("FAILURE_MODE", "")

    settings = Settings()  # type: ignore[call-arg]

    assert settings.otel_endpoint is None
    assert settings.failure_mode is None


def test_blank_required_settings_are_still_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required settings have no meaningful "blank", so they keep failing fast."""
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_non_blank_invalid_optional_settings_are_still_rejected() -> None:
    """Normalising blanks must not weaken validation of real values."""
    with pytest.raises(ValidationError):
        Settings(
            database_url=_TEST_DB_URL,
            redis_url=_TEST_REDIS_URL,
            otel_endpoint="not-a-url",  # type: ignore[arg-type]
        )
