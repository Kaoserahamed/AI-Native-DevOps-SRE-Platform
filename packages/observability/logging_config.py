"""Centralized logging configuration with structured output.

This module provides a standardized logging setup for all services
with JSON formatting, correlation ID support, and Sentry integration.
"""

import logging
import logging.config
import sys
from typing import Any

import structlog


def configure_logging(
    level: str = "INFO",
    service_name: str = "unknown",
    environment: str = "development",
    enable_sentry: bool = False,
    sentry_dsn: str | None = None,
) -> None:
    """Configure structured logging for the application.
    
    Parameters
    ----------
    level
        Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    service_name
        Service identifier for log context
    environment
        Environment name (development, staging, production)
    enable_sentry
        Whether to enable Sentry error tracking
    sentry_dsn
        Sentry DSN for error reporting
    """
    # Standard library logging configuration
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    # Structlog processors for JSON output
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Add service context
    processors.append(
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        )
    )
    
    # JSON formatting for production, console for development
    if environment == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Initialize Sentry if enabled
    if enable_sentry and sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration
            
            sentry_logging = LoggingIntegration(
                level=logging.INFO,  # Capture info and above as breadcrumbs
                event_level=logging.ERROR,  # Send errors as events
            )
            
            sentry_sdk.init(
                dsn=sentry_dsn,
                environment=environment,
                traces_sample_rate=0.1 if environment == "production" else 1.0,
                profiles_sample_rate=0.1 if environment == "production" else 1.0,
                integrations=[sentry_logging],
                send_default_pii=False,  # Don't send PII
                attach_stacktrace=True,
                before_send=_sentry_before_send,
            )
            
            logging.info("Sentry error tracking initialized", dsn_host=sentry_dsn.split("@")[1] if "@" in sentry_dsn else "unknown")
        except ImportError:
            logging.warning("Sentry SDK not installed; error tracking disabled")
        except Exception as e:
            logging.error("Failed to initialize Sentry", error=str(e))


def _sentry_before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Filter and modify events before sending to Sentry.
    
    This prevents sending sensitive information and filters out
    expected errors that shouldn't trigger alerts.
    """
    # Filter out expected errors
    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]
        
        # Don't send validation errors to Sentry
        if exc_type.__name__ in ["ValidationError", "HTTPException"]:
            return None
    
    # Redact sensitive fields
    if "request" in event:
        if "headers" in event["request"]:
            headers = event["request"]["headers"]
            for key in ["Authorization", "Cookie", "X-API-Key"]:
                if key in headers:
                    headers[key] = "[REDACTED]"
    
    return event


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a configured logger instance.
    
    Parameters
    ----------
    name
        Logger name (usually __name__)
    
    Returns
    -------
    structlog.BoundLogger
        Configured logger instance
    """
    return structlog.get_logger(name)


def bind_correlation_id(correlation_id: str) -> None:
    """Bind correlation ID to current context.
    
    This makes the correlation ID available to all subsequent log
    statements in the current execution context.
    
    Parameters
    ----------
    correlation_id
        Request correlation ID
    """
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)


def bind_trace_context(trace_id: str, span_id: str) -> None:
    """Bind OpenTelemetry trace context to logs.
    
    Parameters
    ----------
    trace_id
        OpenTelemetry trace ID
    span_id
        OpenTelemetry span ID
    """
    structlog.contextvars.bind_contextvars(
        trace_id=trace_id,
        span_id=span_id,
    )


def unbind_context() -> None:
    """Clear all context variables.
    
    Should be called at the end of each request to prevent
    context leakage between requests.
    """
    structlog.contextvars.clear_contextvars()
