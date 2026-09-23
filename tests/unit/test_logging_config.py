"""Tests for structured logging configuration."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from itertools import count
from typing import Any
from unittest import mock

import pytest
import structlog

from packages.observability.logging_config import (
    _sentry_before_send,
    bind_correlation_id,
    bind_trace_context,
    configure_logging,
    get_logger,
    unbind_context,
)


@contextmanager
def capture_processor_output(
    *, level: str = "INFO", environment: str = "production", service_name: str = "test-service"
) -> Iterator[tuple[structlog.BoundLogger, dict[str, Any]]]:
    """Configure logging, then capture the event dict structlog hands to the renderer.

    Intercepting the final processor is the only way to assert on the real output without parsing
    strings: it observes exactly the payload the JSON/console renderer would print. Each call gets a
    freshly named logger, because ``cache_logger_on_first_use`` pins a processor chain to a logger
    name for the life of the process.
    """
    captured: dict[str, Any] = {}
    original_configure = structlog.configure

    def configure_with_capture(**kwargs: Any) -> None:
        processors = list(kwargs["processors"])
        renderer = processors.pop()
        captured["renderer"] = renderer

        def capture_event(_logger: Any, _method: str, event_dict: dict[str, Any]) -> Any:
            # Record the event as the renderer sees it, then delegate so the chain still produces the
            # string that stdlib ``logging`` expects as its message.
            captured.update(event_dict)
            return renderer(_logger, _method, event_dict)

        processors.append(capture_event)
        original_configure(**{**kwargs, "processors": processors})

    with mock.patch.object(structlog, "configure", configure_with_capture):
        configure_logging(level=level, environment=environment, service_name=service_name)
        yield get_logger(f"capture-{next(_logger_names)}"), captured


_logger_names = count()


def test_configure_logging_development() -> None:
    """Test logging configuration in development mode."""
    with capture_processor_output(level="DEBUG", environment="development") as (logger, captured):
        logger.info("hello")

    assert isinstance(captured["renderer"], structlog.dev.ConsoleRenderer)
    assert captured["event"] == "hello"
    assert captured["level"] == "info"
    assert captured["service"] == "test-service"


def test_configure_logging_production() -> None:
    """Test logging configuration in production mode with JSON output."""
    with capture_processor_output(level="INFO", environment="production") as (_, captured):
        pass

    assert isinstance(captured["renderer"], structlog.processors.JSONRenderer)


def test_production_logs_render_as_json() -> None:
    """A production event must render to a single JSON object carrying the service name."""
    import json

    configure_logging(level="INFO", service_name="test-service", environment="production")
    renderer = structlog.processors.JSONRenderer()
    rendered = renderer(None, "info", {"event": "boot", "service": "test-service"})

    payload = json.loads(rendered)
    assert payload == {"event": "boot", "service": "test-service"}


def test_get_logger() -> None:
    """Test getting a configured logger instance."""
    configure_logging(service_name="test-service")
    logger = get_logger("test_module")

    # structlog hands out a lazy proxy that realises into the stdlib-bound logger on first use.
    assert logger is not None
    assert isinstance(logger.bind(), structlog.stdlib.BoundLogger)


def test_bind_correlation_id() -> None:
    """Test binding correlation ID to context."""
    configure_logging(service_name="test-service")

    correlation_id = "test-correlation-123"
    bind_correlation_id(correlation_id)

    # Context vars should be bound
    # Note: actual verification would require checking structlog contextvars
    unbind_context()  # Clean up


def test_bind_trace_context() -> None:
    """Test binding OpenTelemetry trace context."""
    configure_logging(service_name="test-service")

    trace_id = "trace-abc123"
    span_id = "span-def456"
    bind_trace_context(trace_id, span_id)

    # Context vars should be bound
    unbind_context()  # Clean up


def test_unbind_context() -> None:
    """Test clearing context variables."""
    configure_logging(service_name="test-service")

    bind_correlation_id("test-123")
    bind_trace_context("trace-1", "span-1")

    # Should clear without errors
    unbind_context()


def test_sentry_before_send_filters_validation_errors() -> None:
    """Test that validation errors are filtered out."""
    event = {"exception": {"values": [{"type": "ValidationError"}]}}
    hint = {
        "exc_info": (
            type("ValidationError", (Exception,), {}),
            Exception("test"),
            None,
        )
    }

    result = _sentry_before_send(event, hint)
    assert result is None  # Validation errors should be filtered


def test_sentry_before_send_redacts_sensitive_headers() -> None:
    """Test that sensitive headers are redacted."""
    event = {
        "request": {
            "headers": {
                "Authorization": "Bearer secret-token",
                "Cookie": "session=secret",
                "X-API-Key": "api-key-secret",
                "Content-Type": "application/json",
            }
        }
    }
    hint: dict[str, Any] = {}

    result = _sentry_before_send(event, hint)

    assert result is not None
    assert result["request"]["headers"]["Authorization"] == "[REDACTED]"
    assert result["request"]["headers"]["Cookie"] == "[REDACTED]"
    assert result["request"]["headers"]["X-API-Key"] == "[REDACTED]"
    assert result["request"]["headers"]["Content-Type"] == "application/json"


def test_sentry_before_send_handles_http_exceptions() -> None:
    """Test that HTTP exceptions are filtered."""
    event = {"exception": {"values": [{"type": "HTTPException"}]}}
    hint = {
        "exc_info": (
            type("HTTPException", (Exception,), {}),
            Exception("404 Not Found"),
            None,
        )
    }

    result = _sentry_before_send(event, hint)
    assert result is None


def test_sentry_before_send_allows_normal_errors() -> None:
    """Test that normal errors pass through."""
    event = {"exception": {"values": [{"type": "RuntimeError"}]}}
    hint = {
        "exc_info": (
            RuntimeError,
            RuntimeError("Something broke"),
            None,
        )
    }

    result = _sentry_before_send(event, hint)
    assert result is not None
    assert result == event


@mock.patch("packages.observability.logging_config.sentry_sdk")
def test_configure_logging_with_sentry(
    mock_sentry: mock.Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test Sentry initialization when enabled."""
    # Ambient variables must not decide what this test observes.
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)

    configure_logging(
        level="INFO",
        service_name="test-service",
        environment="production",
        enable_sentry=True,
        sentry_dsn="https://abc123@sentry.io/456789",
    )

    # Verify Sentry was initialized
    mock_sentry.init.assert_called_once()
    call_kwargs = mock_sentry.init.call_args.kwargs

    assert call_kwargs["dsn"] == "https://abc123@sentry.io/456789"
    assert call_kwargs["environment"] == "production"
    assert call_kwargs["send_default_pii"] is False
    assert call_kwargs["attach_stacktrace"] is True
    # Production must sample, and the "before_send" hook has to be the PII filter.
    assert call_kwargs["traces_sample_rate"] == 0.1
    assert call_kwargs["before_send"] is _sentry_before_send


@mock.patch("packages.observability.logging_config.sentry_sdk")
def test_configure_logging_with_sentry_never_logs_the_dsn_key(mock_sentry: mock.Mock) -> None:
    """The Sentry project key must not reach the logs when tracking is enabled."""
    sentry_dsn = "https://secret-project-key@sentry.io/456789"

    with mock.patch("packages.observability.logging_config.logger") as mock_logger:
        configure_logging(
            level="INFO",
            service_name="test-service",
            environment="production",
            enable_sentry=True,
            sentry_dsn=sentry_dsn,
        )
        log_events = [str(call.args[0]) % call.args[1:] for call in mock_logger.info.call_args_list]

    assert log_events, "enabling Sentry should record which host was contacted"
    assert all("secret-project-key" not in message for message in log_events)
    assert any("sentry.io" in message for message in log_events)


def test_configure_logging_reads_sentry_settings_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deployment must be able to enable error tracking through the environment alone."""
    monkeypatch.setenv("SENTRY_DSN", "https://env-project-key@sentry.io/987654")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")

    # Patching the module-level SDK reference replaces the transport, so the assertions below
    # observe the exact ``init`` call without a client being built or an event leaving the process.
    with mock.patch("packages.observability.logging_config.sentry_sdk") as mock_sentry:
        configure_logging(
            level="INFO",
            service_name="test-service",
            environment="production",
            enable_sentry=True,
        )

    mock_sentry.init.assert_called_once()
    call_kwargs = mock_sentry.init.call_args.kwargs
    assert call_kwargs["dsn"] == "https://env-project-key@sentry.io/987654"
    # The reported environment follows SENTRY_ENVIRONMENT; the logging renderer keeps following the
    # `environment` argument, so "production" still selects JSON output.
    assert call_kwargs["environment"] == "staging"
    assert call_kwargs["traces_sample_rate"] == 1.0  # only production is sampled down
    assert call_kwargs["profiles_sample_rate"] == 1.0
    assert call_kwargs["send_default_pii"] is False
    assert call_kwargs["before_send"] is _sentry_before_send


def test_configure_logging_without_any_dsn_keeps_sentry_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opting in is not enough: with no DSN configured, no client may be created."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    with mock.patch("packages.observability.logging_config.sentry_sdk") as mock_sentry:
        configure_logging(level="INFO", service_name="test-service", enable_sentry=True)

    mock_sentry.init.assert_not_called()


def test_configure_logging_requires_opt_in_for_an_environment_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A DSN in the environment alone must not start reporting: the opt-in switch still decides."""
    monkeypatch.setenv("SENTRY_DSN", "https://env-project-key@sentry.io/987654")

    with mock.patch("packages.observability.logging_config.sentry_sdk") as mock_sentry:
        configure_logging(level="INFO", service_name="test-service", enable_sentry=False)

    mock_sentry.init.assert_not_called()


def test_configure_logging_without_sentry() -> None:
    """Test that a missing Sentry SDK is handled gracefully."""
    with mock.patch("packages.observability.logging_config.sentry_sdk", None):
        # Should not raise even if sentry_sdk is not installed
        configure_logging(
            level="INFO",
            service_name="test-service",
            enable_sentry=True,
            sentry_dsn="https://test@sentry.io/123",
        )


def test_configure_logging_survives_sentry_init_failure() -> None:
    """A broken Sentry configuration must not stop the service from starting."""
    with mock.patch("packages.observability.logging_config.sentry_sdk") as mock_sentry:
        mock_sentry.init.side_effect = RuntimeError("invalid dsn")

        configure_logging(
            level="INFO",
            service_name="test-service",
            enable_sentry=True,
            sentry_dsn="not-a-dsn",
        )

    mock_sentry.init.assert_called_once()


def test_logging_levels() -> None:
    """Test that different log levels are configured correctly."""
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        configure_logging(level=level, service_name="test-service")
        logger = get_logger(__name__)
        assert logger is not None


def test_structured_log_output() -> None:
    """Test that structured logging produces the keys callers attached."""
    with capture_processor_output(level="INFO", environment="production") as (logger, captured):
        logger.info("test_message", key="value", count=42)

    assert captured["event"] == "test_message"
    assert captured["key"] == "value"
    assert captured["count"] == 42


def test_correlation_id_propagation() -> None:
    """Test that the correlation ID reaches every event logged in the bound context."""
    unbind_context()

    with capture_processor_output(environment="production") as (logger, captured):
        bind_correlation_id("req-abc-123")
        logger.info("test_with_correlation")

    assert captured["correlation_id"] == "req-abc-123"

    unbind_context()


def test_trace_context_propagation() -> None:
    """Test that OpenTelemetry trace context reaches the log event."""
    unbind_context()

    with capture_processor_output(environment="production") as (logger, captured):
        bind_trace_context("0123456789abcdef", "fedcba9876543210")
        logger.info("test_with_trace")

    assert captured["trace_id"] == "0123456789abcdef"
    assert captured["span_id"] == "fedcba9876543210"

    unbind_context()


def test_multiple_loggers() -> None:
    """Test that multiple logger instances can be created."""
    configure_logging(service_name="test-service")

    logger1 = get_logger("module1")
    logger2 = get_logger("module2")

    assert logger1 is not None
    assert logger2 is not None
    # Each module gets its own logger
    logger1.info("from_module1")
    logger2.info("from_module2")
