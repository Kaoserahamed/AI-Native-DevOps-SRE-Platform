# syntax=docker/dockerfile:1.9
#
# Demo frontend image (apps/demo-app/frontend), built from the Next.js standalone output.
#
# The build context is the repository root: the frontend is an npm workspace whose dependencies are
# hoisted to the root, and the file tracer starts at the repository root (see next.config.ts):
#
#   docker build -f apps/demo-app/frontend/Dockerfile \
#     --build-arg APP_VERSION=0.1.0 --build-arg VCS_REF="$(git rev-parse HEAD)" \
#     -t demo-frontend:dev .
#
# The runtime stage holds only the traced server and its assets: no npm, no sources, no toolchain.
# The COPY paths below depend on the standalone layout, which `tests/e2e/smoke.mjs` verifies against the
# real build (it derives the entrypoint from `.next/required-server-files.json`).

ARG NODE_VERSION=20.19

# --- dependencies -----------------------------------------------------------------------------------
FROM node:${NODE_VERSION}-bookworm-slim AS dependencies

ENV npm_config_audit=false \
    npm_config_fund=false \
    npm_config_update_notifier=false \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /repo

# Manifests first: the dependency layer survives source-only changes.
COPY package.json package-lock.json ./
COPY apps/demo-app/frontend/package.json apps/demo-app/frontend/package.json
RUN npm ci

# --- builder ----------------------------------------------------------------------------------------
FROM dependencies AS builder

COPY tsconfig.base.json ./
COPY apps/demo-app/frontend/ apps/demo-app/frontend/
# `public/` exists in the repository only once the application ships static files; creating it here keeps
# the runtime COPY below valid either way.
RUN mkdir -p apps/demo-app/frontend/public \
 && npm run build --workspace @demo-app/frontend

# --- runtime ----------------------------------------------------------------------------------------
FROM node:${NODE_VERSION}-bookworm-slim AS runtime

ARG APP_VERSION=0.0.0
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="AI-Native DevOps & SRE Platform demo frontend" \
      org.opencontainers.image.description="Next.js operator view for the demo workload (status, inventory, request correlation)" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/Kaoserahamed/AI-Native-DevOps-SRE-Platform"

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --home-dir /app app

WORKDIR /app

# The workspace-relative path inside the standalone directory is a consequence of tracing from the
# repository root, so the traced server lands at `apps/demo-app/frontend/server.js`.
COPY --from=builder --chown=app:app /repo/apps/demo-app/frontend/.next/standalone/ ./
COPY --from=builder --chown=app:app /repo/apps/demo-app/frontend/.next/static/ ./apps/demo-app/frontend/.next/static/
COPY --from=builder --chown=app:app /repo/apps/demo-app/frontend/public/ ./apps/demo-app/frontend/public/

USER app
EXPOSE 3000

# The page renders server-side without the backend (the panels fetch in the browser), so this check
# exercises the image rather than the demo API.
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:' + (process.env.PORT || '3000') + '/').then((response) => process.exit(response.ok ? 0 : 1)).catch(() => process.exit(1))"]

CMD ["node", "apps/demo-app/frontend/server.js"]
