"""Structured JSON logging setup for the demo API.

Every log record carries the request correlation ID (when available), the
service name and version, and the environment, so logs can be correlated
across the observability stack.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from pythonjsonlogger import json


class CorrelationFilter(logging.Filter):
    """Attach the current request correlation ID to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Inject the correlation ID from a contextvar if present."""
        from services.demo_api.middleware.correlation import get_correlation_id

        correlation_id = get_correlation_id()
        record.correlation_id = correlation_id or "none"
        return True


def configure_logging(
    log_level: int = logging.INFO,
    app_name: str = "demo-api",
    app_version: str = "0.1.0",
    app_env: str = "development",
) -> logging.Logger:
    """Configure root-level structured JSON logging and return the app logger."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any pre-existing handlers so we own the output format.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.addFilter(CorrelationFilter())

    formatter = json.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(correlation_id)s "
        f"{app_name} {app_version} {app_env} %(message)s",
        timestamp=True,
        rename_fields={"levelname": "level", "name": "logger"},
        json_default=str,
        json_serializer=lambda obj: __import__("json").dumps(obj, default=str),
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    app_logger = logging.getLogger(app_name)
    app_logger.setLevel(log_level)
    return app_logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger, lazily ensuring logging is configured."""
    logger = logging.getLogger(name or "demo-api")
    if not logger.handlers and not logging.getLogger().handlers:
        configure_logging()
    return logger


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a structured log event with the standard fields."""
    logger.log(level, message, extra={"extra": extra or {}})
