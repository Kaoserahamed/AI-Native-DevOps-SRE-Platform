/**
 * Deterministic HTTP doubles and fixtures for frontend unit tests.
 *
 * The suites stub `fetch` instead of mocking the API module: that keeps the real typed client in the
 * loop (URL building, headers, correlation IDs, error mapping) while every test stays offline, instant
 * and independent of a running backend.
 */

import type { Mock } from "vitest";
import { vi } from "vitest";

import type { HealthStatus, Item, ReadinessStatus } from "@/lib/api";

/** The `fetch` signature the tests replace. */
export type FetchImpl = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

/** A Vitest mock of `fetch`. */
export type FetchMock = Mock<FetchImpl>;

/** Fixed timestamp so rendered output is stable across runs and time zones. */
export const FIXED_TIMESTAMP = "2026-01-02T03:04:05.000Z";

export const HEALTH_OK: HealthStatus = { status: "ok", timestamp: FIXED_TIMESTAMP };

export const READINESS_OK: ReadinessStatus = {
  status: "ready",
  timestamp: FIXED_TIMESTAMP,
  checks: { database: true, redis: true },
};

export const READINESS_DEGRADED: ReadinessStatus = {
  status: "not_ready",
  timestamp: FIXED_TIMESTAMP,
  checks: { database: false, redis: true },
};

export const SEEDED_ITEM_ACTIVE: Item = {
  id: 1,
  name: "seeded-item",
  description: "Seeded for tests",
  is_active: true,
  created_at: FIXED_TIMESTAMP,
};

export const SEEDED_ITEM_INACTIVE: Item = {
  id: 2,
  name: "paused-item",
  description: null,
  is_active: false,
  created_at: FIXED_TIMESTAMP,
};

export const SEEDED_ITEMS: Item[] = [SEEDED_ITEM_ACTIVE, SEEDED_ITEM_INACTIVE];

/** Build a JSON response with an optional status code and extra headers. */
export function jsonResponse(
  body: unknown,
  init: { status?: number; headers?: Record<string, string> } = {},
): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
  });
}

/** Replace the global `fetch` for the current test (undo with `vi.unstubAllGlobals()`). */
export function stubFetch(implementation: FetchImpl): FetchMock {
  const mock = vi.fn<FetchImpl>(implementation);
  vi.stubGlobal("fetch", mock);
  return mock;
}

/** Return the URL and init of one captured call, failing loudly when the call did not happen. */
export function fetchCall(mock: FetchMock, index = 0): { url: string; init: RequestInit } {
  const call = mock.mock.calls[index];
  if (call === undefined) {
    throw new Error(
      `fetch was called ${mock.mock.calls.length} time(s); call ${index + 1} was expected`,
    );
  }
  return { url: String(call[0]), init: call[1] ?? {} };
}

/** Read a request header from a captured call. */
export function headerOf(mock: FetchMock, name: string, index = 0): string | null {
  return new Headers(fetchCall(mock, index).init.headers).get(name);
}
