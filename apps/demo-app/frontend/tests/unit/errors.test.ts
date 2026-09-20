/**
 * Unit tests for the operator-facing error descriptions.
 *
 * The UI must never render an unbounded upstream payload or a raw stack trace, so every branch of the
 * mapper is pinned here: the status classes the demo API actually returns, a plain transport failure, and
 * a value that is not an error at all.
 */

import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { describeRequestError } from "@/lib/errors";

describe("describeRequestError", () => {
  it("names the failure class for the statuses the demo API returns", () => {
    expect(describeRequestError(new ApiError(404, {}, null))).toContain("does not exist");
    expect(describeRequestError(new ApiError(422, {}, null))).toContain("rejected the request");
    expect(describeRequestError(new ApiError(503, {}, null))).toContain("temporarily unavailable");
    expect(describeRequestError(new ApiError(500, {}, null))).toContain("server error");
    expect(describeRequestError(new ApiError(418, {}, null))).toContain("unexpected status");
  });

  it("includes the status code for server and unexpected errors", () => {
    expect(describeRequestError(new ApiError(502, {}, null))).toContain("502");
    expect(describeRequestError(new ApiError(409, {}, null))).toContain("409");
  });

  it("falls back to the transport message", () => {
    expect(describeRequestError(new Error("Failed to fetch"))).toBe("Failed to fetch");
  });

  it("falls back to a safe default for empty or non-error values", () => {
    expect(describeRequestError(new Error(""))).toContain("returned no error detail");
    expect(describeRequestError(undefined)).toContain("returned no error detail");
    expect(describeRequestError("boom")).toContain("returned no error detail");
  });
});
