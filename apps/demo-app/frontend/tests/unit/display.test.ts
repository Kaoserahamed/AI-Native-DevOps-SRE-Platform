/**
 * Unit tests for the pure display helpers used by the panels.
 *
 * These functions decide what an operator sees (badge tone, overall verdict, dependency summary) and how
 * an untrusted readiness payload that arrived inside an HTTP 503 body is recognised, so they are pinned
 * here rather than only through rendering.
 */

import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import {
  badgeTone,
  formatTimestamp,
  isReadinessStatus,
  overallStatus,
  readinessFromError,
  summarizeReadiness,
} from "@/lib/display";
import { FIXED_TIMESTAMP, HEALTH_OK, READINESS_DEGRADED, READINESS_OK } from "./support/http";

describe("badgeTone", () => {
  it("maps each tri-state dependency result to a badge tone", () => {
    expect(badgeTone(true)).toBe("badge-ok");
    expect(badgeTone(false)).toBe("badge-bad");
    expect(badgeTone(undefined)).toBe("badge-unknown");
  });
});

describe("formatTimestamp", () => {
  it("returns the raw value when it is not a parseable timestamp", () => {
    expect(formatTimestamp("not-a-timestamp")).toBe("not-a-timestamp");
  });

  it("renders a parseable timestamp in a readable form", () => {
    const formatted = formatTimestamp(FIXED_TIMESTAMP);

    expect(formatted).not.toBe(FIXED_TIMESTAMP);
    expect(formatted).toContain("2026");
  });
});

describe("summarizeReadiness", () => {
  it("lists every dependency with its health", () => {
    expect(summarizeReadiness(READINESS_OK)).toBe("ready (database: healthy, redis: healthy)");
  });

  it("reports unhealthy dependencies", () => {
    expect(summarizeReadiness(READINESS_DEGRADED)).toBe(
      "not_ready (database: unhealthy, redis: healthy)",
    );
  });
});

describe("isReadinessStatus", () => {
  it("accepts a well-formed readiness payload", () => {
    expect(isReadinessStatus(READINESS_OK)).toBe(true);
  });

  it.each([
    ["null", null],
    ["a string", "ready"],
    ["a payload without checks", { status: "ready" }],
    ["a payload with a non-boolean check", { status: "not_ready", checks: { database: "yes" } }],
    ["a payload missing a dependency", { status: "ready", checks: { database: true } }],
  ])("rejects %s", (_label, value) => {
    expect(isReadinessStatus(value)).toBe(false);
  });
});

describe("readinessFromError", () => {
  it("recovers the payload from a 503 readiness response", () => {
    const error = new ApiError(503, READINESS_DEGRADED, "corr-503");

    expect(readinessFromError(error)).toEqual(READINESS_DEGRADED);
  });

  it("ignores a 503 whose detail is not a readiness payload", () => {
    expect(readinessFromError(new ApiError(503, { detail: "boom" }, null))).toBeNull();
  });

  it("ignores non-503 failures and non-API errors", () => {
    expect(readinessFromError(new ApiError(500, READINESS_OK, null))).toBeNull();
    expect(readinessFromError(new Error("Failed to fetch"))).toBeNull();
    expect(readinessFromError("boom")).toBeNull();
  });
});

describe("overallStatus", () => {
  it("reports healthy only when readiness says ready", () => {
    expect(overallStatus(HEALTH_OK, READINESS_OK)).toEqual({
      label: "healthy",
      tone: "badge-ok",
      detail: "ready (database: healthy, redis: healthy)",
    });
  });

  it("reports degraded when a dependency is unhealthy", () => {
    const verdict = overallStatus(HEALTH_OK, READINESS_DEGRADED);

    expect(verdict.label).toBe("degraded");
    expect(verdict.tone).toBe("badge-bad");
    expect(verdict.detail).toContain("database: unhealthy");
  });

  it("reports indeterminate when liveness succeeded but readiness did not", () => {
    expect(overallStatus(HEALTH_OK, null).label).toBe("indeterminate");
  });

  it("reports unknown before any response arrives", () => {
    expect(overallStatus(null, null).tone).toBe("badge-unknown");
  });
});
