/**
 * Pure presentation helpers for the demo frontend.
 *
 * These live outside the API client so the transport layer stays about HTTP, and so every derived label
 * the UI shows is a pure function a unit test can pin without rendering anything.
 */

import type { HealthStatus, ReadinessStatus } from "./api";
import { ApiError } from "./api";

/** CSS class names for the three states a status badge can express. */
export type BadgeTone = "badge-ok" | "badge-bad" | "badge-unknown";

/** Map a tri-state dependency check to a badge tone (`undefined` means "not determined yet"). */
export function badgeTone(healthy: boolean | undefined): BadgeTone {
  if (healthy === undefined) {
    return "badge-unknown";
  }
  if (healthy) {
    return "badge-ok";
  }
  return "badge-bad";
}

/** Render an ISO 8601 timestamp in the viewer's locale, falling back to the raw value. */
export function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(undefined, { timeZoneName: "short" });
}

/** Human-readable one-line summary of a readiness payload. */
export function summarizeReadiness(status: ReadinessStatus): string {
  const parts = Object.entries(status.checks).map(
    ([name, healthy]) => `${name}: ${healthy ? "healthy" : "unhealthy"}`,
  );
  return `${status.status} (${parts.join(", ")})`;
}

/**
 * Return whether an untrusted value is a readiness payload.
 *
 * The readiness endpoint answers HTTP 503 with its payload in the error body, so the payload arrives as
 * an {@link ApiError} detail and must be validated before use.
 */
export function isReadinessStatus(value: unknown): value is ReadinessStatus {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as { status?: unknown; checks?: unknown };
  if (typeof candidate.status !== "string") {
    return false;
  }
  if (typeof candidate.checks !== "object" || candidate.checks === null) {
    return false;
  }
  const checks = candidate.checks as Record<string, unknown>;
  return typeof checks["database"] === "boolean" && typeof checks["redis"] === "boolean";
}

/**
 * Extract a readiness payload from a rejected readiness request.
 *
 * A 503 from `GET /ready` is a *result*, not a transport failure: the body lists exactly which
 * dependency is unhealthy, which is the information an operator needs.
 */
export function readinessFromError(error: unknown): ReadinessStatus | null {
  if (error instanceof ApiError && error.status === 503 && isReadinessStatus(error.detail)) {
    return error.detail;
  }
  return null;
}

/** Overall service verdict derived from the liveness and readiness results. */
export interface OverallStatus {
  label: string;
  tone: BadgeTone;
  detail: string;
}

/** Combine liveness and readiness into one verdict for the status header. */
export function overallStatus(
  health: HealthStatus | null,
  readiness: ReadinessStatus | null,
): OverallStatus {
  if (readiness !== null) {
    const detail = summarizeReadiness(readiness);
    if (readiness.status !== "ready") {
      return { label: "degraded", tone: "badge-bad", detail };
    }
    return { label: "healthy", tone: "badge-ok", detail };
  }
  if (health !== null) {
    return {
      label: "indeterminate",
      tone: "badge-unknown",
      detail: "Liveness succeeded but readiness could not be determined.",
    };
  }
  return { label: "unknown", tone: "badge-unknown", detail: "No response from the demo API yet." };
}
