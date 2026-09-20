"""Entry point: ``python -m services.demo_api``.

Starts the uvicorn ASGI server with the demo API application. Configuration
is read from environment variables / ``.env`` file.
"""

from __future__ import annotations

import logging

import uvicorn

if __name__ == "__main__":
    from services.demo_api.config import Settings

    settings = Settings()  # type: ignore[call-arg]
    logging.getLogger("demo-api").info(
        "launching uvicorn host=%s port=%s env=%s",
        settings.host,
        settings.port,
        settings.app_env.value,
    )
    uvicorn.run(
        "services.demo_api.app:create_app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=settings.reload and settings.app_env.value == "development",
        factory=True,
    )
