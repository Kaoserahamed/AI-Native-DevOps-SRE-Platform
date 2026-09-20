# Configuration

This document is the single reference for every environment variable the platform reads.
Configuration is introduced by the phase that needs it, together with a `.env.example`
entry; never commit a real `.env` file (`scripts/check_repo_policy.py` fails the build
when one is tracked).

## Demo API service (`services/demo_api`)

All settings are loaded from the environment (with optional `.env` file support) and
validated at startup by the `Settings` model in `services/demo_api/config.py`. Invalid
values fail fast with a `pydantic.ValidationError` instead of a half-running service.

A **blank value for an optional setting means "not configured"**: a Kubernetes ConfigMap key or `.env`
entry that is present but empty (`OTEL_ENDPOINT=`, `FAILURE_MODE=`) is normalised to unset rather than
rejected, because an environment that does not use an optional feature should not have to omit the key.
A blank value for a required setting (`DATABASE_URL`, `REDIS_URL`) still fails startup, and a non-blank
invalid value is rejected as before.

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
| `OTEL_ENDPOINT` | no | empty | OTLP gRPC collector endpoint, e.g. `http://otel-collector:4317`. When blank or empty, traces are written to the console only. |
| `ENABLE_METRICS` | no | `true` | Expose the Prometheus metrics endpoint (`GET /metrics`). |
| `ENABLE_TRACING` | no | `true` | Initialise OpenTelemetry tracing. Set `false` in unit/contract tests. |
| `FAILURE_MODE` | no | empty | Controllable failure mode for testing (`error_rate`, `database_timeout`, `redis_failure`). **Development only** — rejected with a validation error in staging and production. Leave blank to disable. |
| `FAILURE_RATE` | no | `1.0` | Probability (`0.0`-`1.0`) that a request triggers the active failure mode. |

Copy the template and run locally:

```bash
cp .env.example .env
uv run python -m services.demo_api
```

Do not add unrelated keys to that file: `Settings` uses `extra="forbid"`, so an unknown key in `.env`
fails startup with a validation error instead of being ignored. Application code that needs a variable
the model does not declare must declare a field for it in the same change.

## Demo frontend (`apps/demo-app/frontend`)

The frontend is an npm workspace of the repository root and is configured through the process
environment. It does not read the demo API's `.env` file — that file belongs to the API service and is
not loaded by Next.js from the repository root.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `BACKEND_URL` | no | `http://localhost:8000` | Backend base URL, resolved **at request time** by the `/api` proxy route (and by requests issued from the Next.js server runtime), so one immutable image serves every environment. |
| `NEXT_PUBLIC_BACKEND_URL` | no | unset | Fallback base URL used when `BACKEND_URL` is unset. The browser never uses it: client components always call same-origin `/api`, so no CORS configuration is required. |
| `PORT` | no | `3000` | Port for the standalone server produced by `next build` (`node .next/standalone/server.js`). Read by the standalone server, not by the application. |
| `HOSTNAME` | no | `0.0.0.0` | Bind address for the standalone server. |
| `NEXT_TELEMETRY_DISABLED` | no | unset | Set to `1` in containers and CI so the Next.js build never reaches out to the telemetry endpoint. |

### Where frontend variables must not live

`BACKEND_URL` and the other frontend variables deliberately have **no entry in `.env.example`**. That
file becomes the demo API's `.env`, and the API's settings model rejects unknown keys, so a frontend
variable there would break the API at startup. Pass frontend configuration through the shell, the
container environment or the Kubernetes manifest instead (this is also what the deployment manifests
do).

