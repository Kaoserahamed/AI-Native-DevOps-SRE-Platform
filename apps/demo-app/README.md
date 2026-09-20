# Demo application

The demo application is the **target workload** of the platform. It exists so the control loop
(observe → detect → diagnose → propose → approve → remediate) has something real to observe: a service
that talks to PostgreSQL and Redis, emits structured logs, Prometheus metrics and OpenTelemetry traces,
exposes a controllable failure mode, and can be deployed as two revisions whose difference shows up in
telemetry.

| Component | Location | Language | Purpose |
| --- | --- | --- | --- |
| Demo API | `services/demo_api` | Python (FastAPI) | Business endpoints, dependency checks, metrics, failure injection |
| Demo frontend | `apps/demo-app/frontend` | TypeScript (Next.js) | Operator-facing status and inventory views that generate real traffic |

## Demo API

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Liveness probe: the process is running |
| `GET /ready` | Readiness probe: PostgreSQL and Redis are reachable (`503` with a per-dependency payload when they are not) |
| `GET /metrics` | Prometheus exposition of the request, item, cache and failure-injection metrics |
| `GET /items/` | List items (cached in Redis for 60 seconds) |
| `POST /items/` | Create an item (PostgreSQL write, cache invalidation, `201`) |
| `GET /items/{id}` | Read one item (`404` when it does not exist) |
| `DELETE /items/{id}` | Delete an item (`204`) |

Every response carries an `X-Request-ID` correlation header, which is the join key between frontend
activity, backend logs, metrics and traces.

Configuration is environment driven; see
[docs/04-configuration.md](../../docs/04-configuration.md) for the full reference, including the
development-only failure modes (`error_rate`, `database_timeout`, `redis_failure`) that the incident
scenarios inject.

## Demo frontend

The frontend is an npm workspace of the repository root, so a single `npm ci` at the repository root
installs the repository tooling and the frontend dependencies from the one committed
`package-lock.json`.

What it does:

- **Service status panel** — calls `GET /health` and `GET /ready`, shows a verdict badge
  (healthy / degraded / indeterminate / unknown), per-dependency checks, the loading state, and one error
  banner when the API is unreachable. A `503` from `/ready` is treated as a *result* (a dependency is
  unhealthy) rather than a transport error, because that payload is what an operator needs.
- **Items inventory panel** — lists items, creates them from a small form, deletes them, and reports the
  mutation result together with the correlation ID of the request that produced it.
- **Correlation display** — the API client sends `X-Request-ID` when one is supplied and always surfaces
  the response header, so a UI action can be traced into the backend.

Requests from the browser are same-origin: `next.config.ts` rewrites `/api/:path*` to the demo API, so no
CORS configuration is needed and no backend credential is exposed to the browser.

### Configuration

| Variable | Scope | Default | Description |
| --- | --- | --- | --- |
| `BACKEND_URL` | Next.js server runtime and `next build` | `http://localhost:8000` | Rewrite target for `/api/*` and the base URL used by server-side requests. |
| `NEXT_PUBLIC_BACKEND_URL` | Next.js server runtime | unset | Fallback base URL when `BACKEND_URL` is unset. The browser never uses it: it always calls same-origin `/api`. |
| `PORT` | Standalone server | `3000` | Port the standalone server listens on. |
| `HOSTNAME` | Standalone server | `0.0.0.0` | Interface the standalone server binds. |

The demo API's `.env` file is **not** the place for these values: it is that service's settings source and
unknown keys fail startup deliberately (see
[docs/04-configuration.md](../../docs/04-configuration.md#where-frontend-variables-must-not-live)). Pass
frontend configuration through the process environment (shell, container or Kubernetes manifest).

### Commands

Run from `apps/demo-app/frontend`:

| Goal | Command |
| --- | --- |
| Development server | `npm run dev` |
| Production build (`output: "standalone"`) | `npm run build` |
| Start the standalone build | `node .next/standalone/server.js` |
| Unit + component tests | `npm run test` |
| Tests with the coverage gate | `npm run test:coverage` |
| Lint, format check, type check, tests | `npm run verify` |

If the clone path contains `&` (as this workspace path does on Windows), npm cannot launch the local
binaries through `cmd.exe`. Invoke the tool directly instead:

```powershell
node node_modules/vitest/vitest.mjs run --root apps/demo-app/frontend --coverage
```

### Tests

| Suite | Location | Style |
| --- | --- | --- |
| Transport client | `tests/unit/api.test.ts` | Stubs `fetch`, asserts URLs, headers, bodies, `ApiError` mapping |
| Display helpers | `tests/unit/display.test.ts`, `tests/unit/errors.test.ts` | Pure functions, untrusted-payload guards |
| Panels | `tests/unit/status-panel.test.tsx`, `tests/unit/items-panel.test.tsx` | Testing Library against an in-memory fake backend |
| Shell | `tests/unit/layout.test.ts` | Document metadata contract |
| Page smoke (jsdom) | `tests/unit/home-page.test.tsx` | Both panels render and resolve |

Unit tests never need a running backend: they stub `fetch` with the deterministic doubles in
`tests/unit/support/http.ts`. The browser-level and production-build checks live in the repository-wide
`tests/e2e` tier.

The coverage gate is enforced by `vitest.config.ts` thresholds (85% statements, branches, functions and
lines) and runs as part of `npm run verify`.
