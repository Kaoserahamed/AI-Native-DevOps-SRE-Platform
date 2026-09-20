/**
 * Typed client for the demo FastAPI backend.
 *
 * The browser always talks to same-origin `/api/*` routes, which the route handler in
 * `src/app/api/[...path]/route.ts` proxies to the backend at request time, so no CORS configuration is
 * needed and the backend location stays a deployment concern. Server components and scripts talk to the
 * backend directly through `BACKEND_URL`.
 *
 * Every response surface includes the `X-Request-ID` correlation ID so the UI
 * can display it and operators can join frontend activity to backend logs,
 * metrics and traces.
 */

export interface Item {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ItemCreate {
  name: string;
  description?: string;
  is_active?: boolean;
}

export interface HealthStatus {
  status: string;
  timestamp: string;
}

export interface ReadinessChecks {
  database: boolean;
  redis: boolean;
}

export interface ReadinessStatus {
  status: string;
  timestamp: string;
  checks: ReadinessChecks;
}

export interface ApiResult<T> {
  data: T;
  correlationId: string | null;
}

export interface RequestOptions {
  signal?: AbortSignal | undefined;
  correlationId?: string | undefined;
}

export interface FetchOptions extends RequestOptions {
  method?: string | undefined;
  body?: unknown;
}

const CORRELATION_HEADER = "x-request-id";

export class ApiError extends Error {
  readonly status: number;
  readonly correlationId: string | null;
  readonly detail: unknown;

  constructor(status: number, detail: unknown, correlationId: string | null) {
    super(`API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.correlationId = correlationId;
  }
}

/** Base URL for backend requests: relative in the browser, absolute on the server. */
export function getBackendBaseUrl(): string {
  if (typeof window !== "undefined") {
    return "/api";
  }
  const fromEnv = process.env["BACKEND_URL"] ?? process.env["NEXT_PUBLIC_BACKEND_URL"];
  if (fromEnv !== undefined && fromEnv !== "") {
    return fromEnv.replace(/\/+$/, "");
  }
  return "http://localhost:8000";
}

function buildHeaders(correlationId: string | null | undefined): Headers {
  const headers = new Headers({ "Content-Type": "application/json" });
  if (correlationId !== null && correlationId !== undefined && correlationId !== "") {
    headers.set("X-Request-ID", correlationId);
  }
  return headers;
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text === "") {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export async function fetchJson<T>(
  path: string,
  options: FetchOptions = {},
): Promise<ApiResult<T>> {
  const { method = "GET", body, signal, correlationId } = options;
  const url = `${getBackendBaseUrl()}${path}`;
  const init: RequestInit = { method, headers: buildHeaders(correlationId) };
  if (signal !== undefined) {
    init.signal = signal;
  }
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (error) {
    throw new Error(`Could not reach the demo API at ${url}: ${String(error)}`, {
      cause: error,
    });
  }
  const correlation = response.headers.get(CORRELATION_HEADER);
  const payload = await parseBody(response);
  if (!response.ok) {
    throw new ApiError(response.status, payload, correlation);
  }
  return { data: payload as T, correlationId: correlation };
}

export function listItems(options: RequestOptions = {}): Promise<ApiResult<Item[]>> {
  // No trailing slash: Next.js normalises `/api/items/` to `/api/items`, and the proxy resolves the
  // backend's own canonical redirect, so the canonical path avoids a browser-visible redirect entirely.
  return fetchJson<Item[]>("/items", options);
}

export function createItem(
  input: ItemCreate,
  options: RequestOptions = {},
): Promise<ApiResult<Item>> {
  return fetchJson<Item>("/items", { ...options, method: "POST", body: input });
}

export function getItem(itemId: number, options: RequestOptions = {}): Promise<ApiResult<Item>> {
  return fetchJson<Item>(`/items/${itemId}`, options);
}

export async function deleteItem(
  itemId: number,
  options: RequestOptions = {},
): Promise<ApiResult<null>> {
  return fetchJson<null>(`/items/${itemId}`, { ...options, method: "DELETE" });
}

export function getHealth(options: RequestOptions = {}): Promise<ApiResult<HealthStatus>> {
  return fetchJson<HealthStatus>("/health", options);
}

export function getReadiness(options: RequestOptions = {}): Promise<ApiResult<ReadinessStatus>> {
  return fetchJson<ReadinessStatus>("/ready", options);
}
