# Multi-stage Dockerfile for AI-Native DevOps & SRE Platform
# Builds a production-ready container for any service in the platform

# Stage 1: Builder
FROM python:3.11-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

WORKDIR /build

# Copy dependency files
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/
COPY services/ ./services/
COPY scripts/ ./scripts/

# Install dependencies
RUN uv pip install --system --no-cache -e .

# Stage 2: Runtime
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser packages/ ./packages/
COPY --chown=appuser:appuser services/ ./services/
COPY --chown=appuser:appuser scripts/ ./scripts/

# Build-time metadata
ARG APP_VERSION=dev
ARG VCS_REF=unknown
ARG BUILD_DATE
ARG SERVICE_NAME=incident-api

ENV APP_VERSION=${APP_VERSION} \
    VCS_REF=${VCS_REF} \
    SERVICE_NAME=${SERVICE_NAME} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO \
    ENVIRONMENT=production

LABEL org.opencontainers.image.title="AI-Native DevOps & SRE Platform" \
      org.opencontainers.image.description="AI-driven incident detection, analysis, and remediation" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.authors="Kaoser Ahamed <akaoser41@gmail.com>" \
      org.opencontainers.image.source="https://github.com/Kaoserahamed/AI-Native-DevOps-SRE-Platform" \
      org.opencontainers.image.licenses="Apache-2.0"

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import http.client; conn = http.client.HTTPConnection('localhost', 8000); conn.request('GET', '/health'); r = conn.getresponse(); exit(0 if r.status == 200 else 1)"

# Expose default port
EXPOSE 8000

# Default command (can be overridden for different services)
CMD ["python", "-m", "uvicorn", "services.incident_api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
