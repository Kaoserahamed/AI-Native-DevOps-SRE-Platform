# Configuration

This document is the single reference for every environment variable the platform reads.
Configuration is introduced by the phase that needs it, together with a `.env.example`
entry; never commit a real `.env` file (`scripts/check_repo_policy.py` fails the build
when one is tracked).

## Demo API service (`services/demo_api`)

All settings are loaded from the environment (with optional `.env` file support) and
validated at startup by the `Settings` model in `services/demo_api/config.py`. Invalid
values fail fast with a `pydantic.ValidationError` instead of a half-running service.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `APP_NAME` | no | `demo-api` | Service identity used in logs, metrics and traces. |
| `APP_ENV` | no | `development` | One of `development`, `staging`, `production`. Gates test-only flags. |
| `APP_VERSION` | no | `0.1.0` | Semantic version reported in the service-info metric and OpenAPI docs. |
| `HOST` | no | `0.0.0.0` | Bind address for the uvicorn ASGI server. |
| `PORT` | no | `8000` | Listen port (`1`-`65535`). |
| `LOG_LEVEL` | no | `INFO` | Python logging level name (`DEBUG`, `INFO`, `WARNING`, `ERROR`, ...). |
| `RELOAD` | no | `false` | Auto-reload (development only; rejected in staging/production). |
| `DATABASE_URL` | yes | — | PostgreSQL connection string, e.g. `postgresql+asyncpg://user:pass@localhost:5432/demo_api`. |
| `REDIS_URL` | yes | — | Redis connection string, e.g. `redis://localhost:6379/0`. |
| `OTEL_ENDPOINT` | no | empty | OTLP gRPC collector endpoint, e.g. `http://otel-collector:4317`. When empty, traces are written to the console only. |
| `ENABLE_METRICS` | no | `true` | Expose the Prometheus metrics endpoint (`GET /metrics`). |
| `ENABLE_TRACING` | no | `true` | Initialise OpenTelemetry tracing. Set `false` in unit/contract tests. |
| `FAILURE_MODE` | no | empty | Controllable failure mode for testing (`error_rate`, `database_timeout`, `redis_failure`). **Development only** — rejected with a validation error in staging and production. |
| `FAILURE_RATE` | no | `1.0` | Probability (`0.0`-`1.0`) that a request triggers the active failure mode. |

Copy the template and run locally:

```bash
cp .env.example .env
uv run python -m services.demo_api
```
