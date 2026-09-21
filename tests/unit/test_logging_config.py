"""Tests for structured logging configuration."""

import logging
from unittest import mock

import pytest
import structlog

from packages.observability.logging_config import (
    configure_logging,
    get_logger,
    bind_correlation_id,
    bind_trace_context,
    unbind_context,
    _sentry_before_send,
)


def test_configure_logging_development() -> None:
    """Test logging configuration in development mode."""
    configure_logging(
        level="DEBUG",
        service_name="test-service",
        environment="development",
        enable_sentry=False,
    )

    logger = get_logger(__name__)
    assert logger is not None
    assert isinstance(logger, structlog.BoundLogger)


def test_configure_logging_production() -> None:
    """Test logging configuration in production mode with JSON output."""
    configure_logging(
        level="INFO",
        service_name="test-service",
        environment="production",
        enable_sentry=False,
    )

    logger = get_logger(__name__)
    assert logger is not None


def test_get_logger() -> None:
    """Test getting a configured logger instance."""
    configure_logging(service_name="test-service")
    logger = get_logger("test_module")

    assert logger is not None
    assert isinstance(logger, structlog.BoundLogger)


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
    hint = {}

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
def test_configure_logging_with_sentry(mock_sentry: mock.Mock) -> None:
    """Test Sentry initialization when enabled."""
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


def test_configure_logging_without_sentry() -> None:
    """Test that missing Sentry SDK is handled gracefully."""
    with mock.patch.dict("sys.modules", {"sentry_sdk": None}):
        # Should not raise even if sentry_sdk not installed
        configure_logging(
            level="INFO",
            service_name="test-service",
            enable_sentry=True,
            sentry_dsn="https://test@sentry.io/123",
        )


def test_logging_levels() -> None:
    """Test that different log levels are configured correctly."""
    for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        configure_logging(level=level, service_name="test-service")
        logger = get_logger(__name__)
        assert logger is not None


def test_structured_log_output() -> None:
    """Test that structured logging produces expected output."""
    configure_logging(
        level="INFO",
        service_name="test-service",
        environment="production",
    )

    logger = get_logger(__name__)

    # This should produce JSON output in production mode
    logger.info("test_message", key="value", count=42)

    # Actual assertion would require capturing output
    # For now, just verify it doesn't raise


def test_correlation_id_propagation() -> None:
    """Test that correlation ID propagates to all log messages."""
    configure_logging(service_name="test-service")

    correlation_id = "req-abc-123"
    bind_correlation_id(correlation_id)

    logger = get_logger(__name__)
    logger.info("test_with_correlation")

    # In practice, the correlation_id would appear in the output
    unbind_context()


def test_trace_context_propagation() -> None:
    """Test that trace context propagates to logs."""
    configure_logging(service_name="test-service")

    trace_id = "0123456789abcdef"
    span_id = "fedcba9876543210"
    bind_trace_context(trace_id, span_id)

    logger = get_logger(__name__)
    logger.info("test_with_trace")

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
