/**
 * Unit tests for the same-origin API proxy.
 *
 * The proxy is the boundary between the browser-facing frontend and the backend, so its contract is
 * pinned here: URL and query handling, body forwarding, the headers that must not cross the trust
 * boundary, correlation ID propagation in both directions, and bodyless upstream statuses.
 */

import { describe, expect, it, vi } from "vitest";

import type { FetchImpl } from "@/lib/backendProxy";
import {
  CORRELATION_HEADER,
  backendBaseUrl,
  correlationIdFor,
  forwardToBackend,
} from "@/lib/backendProxy";
import { fetchCall, headerOf, jsonResponse } from "./support/http";

const BACKEND = "http://backend.internal";

function upstreamFetch(implementation: FetchImpl) {
  return vi.fn<FetchImpl>(implementation);
}

function forward(
  request: Request,
  path: string[],
  fetchImpl: FetchImpl = upstreamFetch(async () => jsonResponse({ status: "ok" })),
): Promise<Response> {
  return forwardToBackend(request, path, { baseUrl: BACKEND, fetchImpl });
}

describe("backendBaseUrl", () => {
  it("falls back to the local development backend", () => {
    expect(backendBaseUrl({})).toBe("http://localhost:8000");
    expect(backendBaseUrl({ BACKEND_URL: "   " })).toBe("http://localhost:8000");
  });

  it("prefers BACKEND_URL and trims trailing slashes", () => {
    expect(backendBaseUrl({ BACKEND_URL: "http://demo-api:8000//" })).toBe("http://demo-api:8000");
  });

  it("accepts NEXT_PUBLIC_BACKEND_URL as a fallback", () => {
    expect(backendBaseUrl({ NEXT_PUBLIC_BACKEND_URL: "http://fallback:9000" })).toBe(
      "http://fallback:9000",
    );
  });
});

describe("correlationIdFor", () => {
  it("keeps a caller-supplied correlation id", () => {
    const request = new Request("http://frontend.local/api/health", {
      headers: { [CORRELATION_HEADER]: " caller-supplied " },
    });

    expect(correlationIdFor(request)).toBe("caller-supplied");
  });

  it("generates one when the caller supplies none or a blank value", () => {
    const withoutHeader = correlationIdFor(new Request("http://frontend.local/api/health"));
    const withBlankHeader = correlationIdFor(
      new Request("http://frontend.local/api/health", { headers: { [CORRELATION_HEADER]: "  " } }),
    );

    expect(withoutHeader).toMatch(/^[0-9a-f]{32}$/);
    expect(withBlankHeader).toMatch(/^[0-9a-f]{32}$/);
  });
});

describe("forwardToBackend", () => {
  it("forwards a GET to the backend path and returns the upstream payload", async () => {
    const upstream = upstreamFetch(async () => jsonResponse({ status: "ok" }));

    const response = await forward(
      new Request("http://frontend.local/api/health"),
      ["health"],
      upstream,
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ status: "ok" });
    expect(fetchCall(upstream).url).toBe(`${BACKEND}/health`);
    expect(fetchCall(upstream).init.method).toBe("GET");
    expect(fetchCall(upstream).init.body).toBeNull();
  });

  it("preserves the query string and encodes path segments", async () => {
    const upstream = upstreamFetch(async () => jsonResponse([]));

    await forward(
      new Request("http://frontend.local/api/items/a%20b?limit=5&active=true"),
      ["items", "a b"],
      upstream,
    );

    expect(fetchCall(upstream).url).toBe(`${BACKEND}/items/a%20b?limit=5&active=true`);
  });

  it("preserves a trailing slash so collection routes keep their meaning", async () => {
    const upstream = upstreamFetch(async () => jsonResponse([]));

    await forward(new Request("http://frontend.local/api/items/"), ["items"], upstream);

    expect(fetchCall(upstream).url).toBe(`${BACKEND}/items/`);
  });

  it("keeps the path as called when no trailing slash was used", async () => {
    const upstream = upstreamFetch(async () => jsonResponse([]));

    await forward(new Request("http://frontend.local/api/items"), ["items"], upstream);

    expect(fetchCall(upstream).url).toBe(`${BACKEND}/items`);
  });

  it("resolves a canonical redirect the backend issues for its own route", async () => {
    const upstream = upstreamFetch(async (input) =>
      String(input).endsWith("/items/")
        ? jsonResponse([{ id: 1 }])
        : new Response(null, { status: 307, headers: { location: `${BACKEND}/items/` } }),
    );

    const response = await forward(
      new Request("http://frontend.local/api/items"),
      ["items"],
      upstream,
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual([{ id: 1 }]);
    expect(upstream.mock.calls).toHaveLength(2);
    expect(fetchCall(upstream, 1).url).toBe(`${BACKEND}/items/`);
  });

  it("keeps the method and body when following a 307", async () => {
    const upstream = upstreamFetch(async (input) =>
      String(input).endsWith("/items/")
        ? jsonResponse({ id: 2 }, { status: 201 })
        : new Response(null, { status: 307, headers: { location: `${BACKEND}/items/` } }),
    );

    const response = await forward(
      new Request("http://frontend.local/api/items", { method: "POST", body: '{"name":"kept"}' }),
      ["items"],
      upstream,
    );

    expect(response.status).toBe(201);
    expect(fetchCall(upstream, 1).init.method).toBe("POST");
    expect(fetchCall(upstream, 1).init.body).not.toBeNull();
  });

  it("downgrades a 303 to a bodyless GET", async () => {
    const upstream = upstreamFetch(async (input) =>
      String(input).endsWith("/items/")
        ? jsonResponse({ ok: true })
        : new Response(null, { status: 303, headers: { location: "/items/" } }),
    );

    await forward(
      new Request("http://frontend.local/api/items", { method: "POST", body: "{}" }),
      ["items"],
      upstream,
    );

    expect(fetchCall(upstream, 1).init.method).toBe("GET");
    expect(fetchCall(upstream, 1).init.body).toBeNull();
  });

  it("passes a redirect to another origin through for the browser to follow", async () => {
    const upstream = upstreamFetch(
      async () =>
        new Response(null, { status: 302, headers: { location: "https://login.example.com/sso" } }),
    );

    const response = await forward(
      new Request("http://frontend.local/api/items"),
      ["items"],
      upstream,
    );

    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe("https://login.example.com/sso");
    expect(upstream.mock.calls).toHaveLength(1);
  });

  it("answers 502 when the backend redirects past the proxy budget", async () => {
    const upstream = upstreamFetch(
      async () => new Response(null, { status: 307, headers: { location: `${BACKEND}/loop` } }),
    );

    const response = await forward(
      new Request("http://frontend.local/api/items"),
      ["items"],
      upstream,
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toMatchObject({
      detail: expect.stringContaining("redirect budget"),
    });
    expect(response.headers.get(CORRELATION_HEADER)).not.toBeNull();
  });

  it("forwards a request body for write methods", async () => {
    const upstream = upstreamFetch(async () => jsonResponse({ id: 1 }, { status: 201 }));

    const response = await forward(
      new Request("http://frontend.local/api/items/", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: "proxied" }),
      }),
      ["items", ""],
      upstream,
    );

    expect(response.status).toBe(201);
    expect(fetchCall(upstream).init.method).toBe("POST");
    const forwarded = new TextDecoder().decode(fetchCall(upstream).init.body as ArrayBuffer);
    expect(forwarded).toBe('{"name":"proxied"}');
    expect(headerOf(upstream, "content-type")).toBe("application/json");
  });

  it("does not forward hop-by-hop or browser-specific headers", async () => {
    const upstream = upstreamFetch(async () => jsonResponse({ status: "ok" }));

    await forward(
      new Request("http://frontend.local/api/health", {
        headers: {
          accept: "application/json",
          "accept-encoding": "gzip, deflate, br",
          connection: "keep-alive",
          host: "frontend.local",
        },
      }),
      ["health"],
      upstream,
    );

    expect(headerOf(upstream, "accept")).toBe("application/json");
    expect(headerOf(upstream, "accept-encoding")).toBeNull();
    expect(headerOf(upstream, "connection")).toBeNull();
    expect(headerOf(upstream, "host")).toBeNull();
  });

  it("carries the correlation id to the backend and prefers the upstream value back", async () => {
    const upstream = upstreamFetch(async () =>
      jsonResponse({ status: "ok" }, { headers: { [CORRELATION_HEADER]: "backend-corr" } }),
    );

    const response = await forward(
      new Request("http://frontend.local/api/health", {
        headers: { [CORRELATION_HEADER]: "frontend-corr" },
      }),
      ["health"],
      upstream,
    );

    expect(headerOf(upstream, CORRELATION_HEADER)).toBe("frontend-corr");
    expect(response.headers.get(CORRELATION_HEADER)).toBe("backend-corr");
  });

  it("returns the generated correlation id when the backend does not answer with one", async () => {
    const upstream = upstreamFetch(async () => new Response(JSON.stringify({ ok: true })));

    const response = await forward(
      new Request("http://frontend.local/api/health"),
      ["health"],
      upstream,
    );

    expect(response.headers.get(CORRELATION_HEADER)).toMatch(/^[0-9a-f]{32}$/);
  });

  it("drops entity headers that no longer describe the relayed body", async () => {
    const upstream = upstreamFetch(
      async () =>
        new Response(JSON.stringify({ ok: true }), {
          headers: {
            "content-encoding": "gzip",
            "content-length": "11",
            "transfer-encoding": "chunked",
          },
        }),
    );

    const response = await forward(
      new Request("http://frontend.local/api/health"),
      ["health"],
      upstream,
    );

    expect(response.headers.get("content-encoding")).toBeNull();
    expect(response.headers.get("content-length")).toBeNull();
    expect(response.headers.get("transfer-encoding")).toBeNull();
  });

  it("relays a bodyless 204 without inventing one", async () => {
    const upstream = upstreamFetch(async () => new Response(null, { status: 204 }));

    const response = await forward(
      new Request("http://frontend.local/api/items/7", { method: "DELETE" }),
      ["items", "7"],
      upstream,
    );

    expect(response.status).toBe(204);
    expect(response.body).toBeNull();
    expect(fetchCall(upstream).init.method).toBe("DELETE");
  });

  it("propagates an unreachable backend as a failure", async () => {
    const upstream = upstreamFetch(async () => {
      throw new TypeError("fetch failed");
    });

    await expect(
      forward(new Request("http://frontend.local/api/health"), ["health"], upstream),
    ).rejects.toThrow("fetch failed");
  });
});
