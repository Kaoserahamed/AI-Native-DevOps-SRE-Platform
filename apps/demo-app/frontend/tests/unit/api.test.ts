/**
 * Unit tests for the typed demo API client.
 *
 * The client is the only place that knows about HTTP, URLs, headers and error shapes, so these tests pin
 * the transport contract: same-origin `/api` routes in the browser, `X-Request-ID` propagation in both
 * directions, JSON bodies for writes, `ApiError` for failed responses and a clear message when the API is
 * unreachable.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createItem, deleteItem, getHealth, getReadiness, listItems } from "@/lib/api";
import {
  FIXED_TIMESTAMP,
  SEEDED_ITEMS,
  SEEDED_ITEM_ACTIVE,
  fetchCall,
  headerOf,
  jsonResponse,
  stubFetch,
} from "./support/http";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("demo API client", () => {
  it("requests same-origin /api routes from the browser", async () => {
    const mock = stubFetch(async () => jsonResponse(SEEDED_ITEMS));

    const result = await listItems();

    expect(fetchCall(mock).url).toBe("/api/items/");
    expect(fetchCall(mock).init.method).toBe("GET");
    expect(result.data).toHaveLength(2);
  });

  it("sends the caller correlation id and returns the response one", async () => {
    const mock = stubFetch(async () =>
      jsonResponse(SEEDED_ITEMS, { headers: { "x-request-id": "response-corr" } }),
    );

    const result = await listItems({ correlationId: "caller-corr" });

    expect(headerOf(mock, "x-request-id")).toBe("caller-corr");
    expect(result.correlationId).toBe("response-corr");
  });

  it("omits the correlation header when none is supplied", async () => {
    const mock = stubFetch(async () => jsonResponse(SEEDED_ITEMS));

    await listItems();

    expect(headerOf(mock, "x-request-id")).toBeNull();
  });

  it("posts JSON bodies for writes", async () => {
    const mock = stubFetch(async () =>
      jsonResponse({ ...SEEDED_ITEM_ACTIVE, name: "chaos-item" }, { status: 201 }),
    );

    const created = await createItem({ name: "chaos-item", description: "generated" });
    const call = fetchCall(mock);

    expect(call.url).toBe("/api/items/");
    expect(call.init.method).toBe("POST");
    expect(headerOf(mock, "content-type")).toContain("application/json");
    expect(JSON.parse(String(call.init.body))).toEqual({
      name: "chaos-item",
      description: "generated",
    });
    expect(created.data.name).toBe("chaos-item");
  });

  it("maps a failed response to an ApiError with status, detail and correlation id", async () => {
    stubFetch(async () =>
      jsonResponse(
        { detail: "failure_mode=error_rate: service temporarily unavailable" },
        { status: 503, headers: { "x-request-id": "error-corr" } },
      ),
    );

    const failure = await listItems().then(
      () => null,
      (cause: unknown) => cause,
    );

    expect(failure).toBeInstanceOf(ApiError);
    const apiError = failure as ApiError;
    expect(apiError.status).toBe(503);
    expect(apiError.detail).toEqual({
      detail: "failure_mode=error_rate: service temporarily unavailable",
    });
    expect(apiError.correlationId).toBe("error-corr");
  });

  it("reports an unreachable API together with the attempted URL", async () => {
    stubFetch(async () => {
      throw new TypeError("Failed to fetch");
    });

    await expect(getHealth()).rejects.toThrow(/Could not reach the demo API at \/api\/health/);
  });

  it("returns null data for empty bodies such as HTTP 204", async () => {
    const mock = stubFetch(async () => new Response(null, { status: 204 }));

    const result = await deleteItem(7);

    expect(fetchCall(mock).url).toBe("/api/items/7");
    expect(fetchCall(mock).init.method).toBe("DELETE");
    expect(result.data).toBeNull();
  });

  it("returns the raw text when a body is not JSON", async () => {
    stubFetch(
      async () =>
        new Response("not json", { status: 200, headers: { "content-type": "text/plain" } }),
    );

    const result = await getReadiness();

    expect(result.data).toBe("not json");
  });

  it("keeps the readiness path and liveness path distinct", async () => {
    const mock = stubFetch(async () =>
      jsonResponse({ status: "ready", timestamp: FIXED_TIMESTAMP }),
    );

    await getReadiness();

    expect(fetchCall(mock).url).toBe("/api/ready");
  });
});
