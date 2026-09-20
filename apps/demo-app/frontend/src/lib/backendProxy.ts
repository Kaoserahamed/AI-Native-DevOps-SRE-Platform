/**
 * Server-side proxy from the demo frontend to the demo API.
 *
 * The browser always calls same-origin `/api/*`, and this module forwards those requests to the backend
 * at request time. Doing it at request time (rather than with a Next.js `rewrites()` entry) is what keeps
 * one immutable image valid in every environment: a rewrite destination is frozen into the build, so it
 * would force a separate frontend image per environment.
 *
 * Responsibilities: resolve the backend base URL from the environment, bound the headers that cross the
 * trust boundary, carry the `X-Request-ID` correlation ID in both directions, and stream the response
 * back without buffering it.
 */

export const CORRELATION_HEADER = "x-request-id";

const DEFAULT_BASE_URL = "http://localhost:8000";

/**
 * Hop-by-hop headers describe the connection, not the message, and must not be forwarded by a proxy.
 * `accept-encoding` is dropped as well because the proxy relays a decoded body, so the backend must
 * answer uncompressed.
 */
const HEADERS_NOT_FORWARDED = [
  "accept-encoding",
  "connection",
  "content-encoding",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
];

/** Signature of the `fetch` implementation the proxy uses (injected in tests). */
export type FetchImpl = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;

/** Options accepted by {@link forwardToBackend}. */
export interface ForwardOptions {
  baseUrl?: string | undefined;
  fetchImpl?: FetchImpl | undefined;
}

/** Resolve the backend base URL from the environment, falling back to the local development default. */
export function backendBaseUrl(env: Record<string, string | undefined> = process.env): string {
  const configured = env["BACKEND_URL"] ?? env["NEXT_PUBLIC_BACKEND_URL"] ?? "";
  const trimmed = configured.trim().replace(/\/+$/, "");
  return trimmed === "" ? DEFAULT_BASE_URL : trimmed;
}

/**
 * Return the correlation ID for a proxied request: the caller's value when it supplies one, otherwise a
 * generated ID so every hop can always be correlated.
 */
export function correlationIdFor(request: Request): string {
  const supplied = request.headers.get(CORRELATION_HEADER);
  if (supplied !== null && supplied.trim() !== "") {
    return supplied.trim();
  }
  return globalThis.crypto.randomUUID().replaceAll("-", "");
}

/** Return the backend URL for a request, preserving the trailing slash the caller used. */
function targetUrl(baseUrl: string, request: Request, path: string[]): URL {
  const incoming = new URL(request.url);
  const segments = path.map(encodeURIComponent).join("/");
  const target = new URL(`${baseUrl}/${segments}`);
  if (segments !== "" && incoming.pathname.endsWith("/")) {
    // `/api/items/` and `/api/items` are different routes for the demo API (a collection versus a
    // redirect), so the proxy must not normalise the trailing slash away.
    target.pathname = `${target.pathname}/`;
  }
  target.search = incoming.search;
  return target;
}

const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308]);

/** Hop budget for redirects a backend issues for its own routes. */
const MAX_REDIRECT_HOPS = 2;

interface UpstreamResult {
  response: Response;
  /** True when the backend kept redirecting within its own origin past the hop budget. */
  redirectBudgetExhausted: boolean;
}

/**
 * Call the backend, resolving the canonical redirects it issues for its own routes.
 *
 * A gateway must not hand an API client a 3xx that only exists for canonicalisation (FastAPI redirects
 * `/items` to `/items/`, for example): the client would be sent to a URL in the backend's address space.
 * Those redirects are resolved here instead, bounded to a small hop budget and restricted to the
 * backend's own origin, so a `Location` chosen by the backend can never steer the proxy to another host
 * (server-side request forgery). Redirects to *other* origins are legitimate — an identity provider, for
 * example — and are passed through for the browser to follow.
 */
async function fetchUpstream(
  fetchImpl: FetchImpl,
  target: URL,
  init: RequestInit,
  backendOrigin: string,
): Promise<UpstreamResult> {
  let currentUrl = target;
  let method = (init.method ?? "GET").toUpperCase();
  let body: BodyInit | null = init.body ?? null;
  let response = await fetchImpl(currentUrl, { ...init, method, body });
  let hops = 0;

  while (REDIRECT_STATUSES.has(response.status) && hops < MAX_REDIRECT_HOPS) {
    const location = response.headers.get("location");
    if (location === null) {
      break;
    }
    const next = new URL(location, currentUrl);
    if (next.origin !== backendOrigin) {
      break;
    }
    hops += 1;
    if (
      response.status === 303 ||
      (response.status < 304 && method !== "GET" && method !== "HEAD")
    ) {
      // 301/302/303 turn a write into a GET without a body, exactly as an HTTP client would.
      method = "GET";
      body = null;
    }
    currentUrl = next;
    response = await fetchImpl(currentUrl, { ...init, method, body });
  }

  let redirectBudgetExhausted = false;
  if (REDIRECT_STATUSES.has(response.status)) {
    const location = response.headers.get("location");
    redirectBudgetExhausted =
      location !== null && new URL(location, currentUrl).origin === backendOrigin;
  }

  return { response, redirectBudgetExhausted };
}

/** Forward one request to the backend and return its response. */
export async function forwardToBackend(
  request: Request,
  path: string[],
  options: ForwardOptions = {},
): Promise<Response> {
  const baseUrl = options.baseUrl ?? backendBaseUrl();
  const fetchImpl = options.fetchImpl ?? fetch;
  const target = targetUrl(baseUrl, request, path);

  const headers = new Headers(request.headers);
  for (const header of HEADERS_NOT_FORWARDED) {
    headers.delete(header);
  }
  const correlationId = correlationIdFor(request);
  headers.set(CORRELATION_HEADER, correlationId);

  const method = request.method.toUpperCase();
  const sendsBody = !["GET", "HEAD", "OPTIONS"].includes(method);
  const init: RequestInit = { method, headers, redirect: "manual", cache: "no-store" };
  if (sendsBody) {
    init.body = await request.arrayBuffer();
  }

  const { response: upstream, redirectBudgetExhausted } = await fetchUpstream(
    fetchImpl,
    target,
    init,
    new URL(baseUrl).origin,
  );

  if (redirectBudgetExhausted) {
    // Never hand the client a `Location` inside the backend's address space.
    console.error(
      `api proxy: backend exceeded the redirect budget for ${target.pathname} (correlation ${correlationId})`,
    );
    return new Response(
      JSON.stringify({
        detail: "the backend exceeded the proxy redirect budget",
        correlation_id: correlationId,
      }),
      {
        status: 502,
        headers: { "content-type": "application/json", [CORRELATION_HEADER]: correlationId },
      },
    );
  }

  // Headers the proxy must not repair: the body is relayed as received, so entity headers the backend
  // sent for the wire encoding do not apply any more.
  const responseHeaders = new Headers(upstream.headers);
  for (const header of ["content-encoding", "content-length", "transfer-encoding"]) {
    responseHeaders.delete(header);
  }
  responseHeaders.set(
    CORRELATION_HEADER,
    upstream.headers.get(CORRELATION_HEADER) ?? correlationId,
  );

  const bodyless = upstream.status === 204 || upstream.status === 304;
  return new Response(bodyless ? null : upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
