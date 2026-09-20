# syntax=docker/dockerfile:1.9
#
# Demo API image (services/demo_api).
#
# The build context is the repository root, because the service belongs to the single Python project
# defined by `pyproject.toml` + `uv.lock`:
#
#   docker build -f services/demo_api/Dockerfile \
#     --build-arg APP_VERSION=0.1.0 --build-arg VCS_REF="$(git rev-parse HEAD)" \
#     -t demo-api:dev .
#
# Two stages: a builder that resolves the locked dependency set with `uv`, and a slim runtime that
# receives the virtual environment and the sources — never uv, compilers or package caches.

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.12.17

# --- builder: resolve the locked dependencies -------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ARG UV_VERSION

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# uv is pinned to an exact version installed from PyPI, never fetched by a floating install script.
RUN pip install --no-cache-dir "uv==${UV_VERSION}"

WORKDIR /build

# Dependencies first, so this layer only invalidates when the lockfile changes.
COPY pyproject.toml uv.lock README.md LICENSE ./
# The project itself is deliberately not installed: an editable install would point at /build, which does
# not exist in the runtime stage. The runtime copies the sources instead and relies on the working
# directory being `/app`, which is where `python -m services.demo_api` resolves `services` and `packages`.
RUN uv sync --frozen --no-dev --no-install-project

COPY packages/ packages/
COPY services/ services/
COPY scripts/ scripts/

# --- runtime ----------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG APP_VERSION=0.0.0
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="AI-Native DevOps & SRE Platform demo API" \
      org.opencontainers.image.description="Observable FastAPI demo workload for the AI-native incident control loop" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/Kaoserahamed/AI-Native-DevOps-SRE-Platform"

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    APP_ENV=production \
    HOST=0.0.0.0 \
    PORT=8000

# Unprivileged account without a home directory. `PYTHONDONTWRITEBYTECODE=1` means the process writes no
# `.pyc` files, which is what makes a read-only root filesystem workable.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --home-dir /app app

WORKDIR /app
COPY --from=builder --chown=app:app /build/.venv /app/.venv
COPY --from=builder --chown=app:app /build/packages /app/packages
COPY --from=builder --chown=app:app /build/services /app/services

USER app
EXPOSE 8000

# No curl in a slim image: the runtime can probe itself, and adding a downloader would widen the surface
# of every image for a check that does not need one.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=2)"]

# Same entry point as a local process, so configuration comes from the environment in both cases
# (docs/04-configuration.md). DATABASE_URL and REDIS_URL are required: the container fails fast instead
# of starting half-configured.
ENTRYPOINT ["python", "-m", "services.demo_api"]
