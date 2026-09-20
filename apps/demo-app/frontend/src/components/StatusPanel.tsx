"use client";

/**
 * Liveness and readiness view for the demo workload.
 *
 * This is the panel an operator opens first during an incident: it distinguishes "the process is alive"
 * from "the pod is ready to serve traffic" (PostgreSQL and Redis reachable) and always shows the request
 * correlation ID, so the same request can be found in backend logs, metrics and traces.
 */

import { useCallback } from "react";

import type { HealthStatus, ReadinessStatus } from "@/lib/api";
import { getHealth, getReadiness } from "@/lib/api";
import { badgeTone, formatTimestamp, overallStatus, readinessFromError } from "@/lib/display";
import { describeRequestError } from "@/lib/errors";
import { useApiResource } from "@/lib/useApiResource";

const DEPENDENCIES = ["database", "redis"] as const;

/** Render the liveness/readiness card. */
export function StatusPanel() {
  const loadHealth = useCallback((signal: AbortSignal) => getHealth({ signal }), []);
  const loadReadiness = useCallback((signal: AbortSignal) => getReadiness({ signal }), []);

  const health = useApiResource<HealthStatus>(loadHealth);
  const readiness = useApiResource<ReadinessStatus>(loadReadiness);

  // A 503 readiness response carries the dependency breakdown, so it is displayed as a degraded result
  // rather than as a transport error. Any other failure is reported as an error banner.
  const readinessPayload = readiness.data ?? readinessFromError(readiness.error);

  // At most one banner is shown: readiness is the signal an operator acts on, so its failure wins, and a
  // liveness failure is reported only when readiness itself succeeded.
  let failureMessage: string | null = null;
  if (!readiness.isLoading && readinessPayload === null && readiness.error !== null) {
    failureMessage = describeRequestError(readiness.error);
  } else if (!health.isLoading && health.error !== null) {
    failureMessage = describeRequestError(health.error);
  }

  const isLoading = health.isLoading || readiness.isLoading;
  const status = overallStatus(health.data, readinessPayload);
  const lastChecked = readinessPayload?.timestamp ?? health.data?.timestamp ?? null;
  const correlationId = readiness.correlationId ?? health.correlationId;

  const reloadHealth = health.reload;
  const reloadReadiness = readiness.reload;
  const refresh = useCallback(() => {
    reloadHealth();
    reloadReadiness();
  }, [reloadHealth, reloadReadiness]);

  return (
    <section className="card" aria-labelledby="status-heading" data-testid="status-panel">
      <h2 id="status-heading">Service status</h2>
      <p className="muted">
        Liveness comes from <code>GET /health</code>; readiness comes from <code>GET /ready</code>,
        which checks PostgreSQL and Redis before Kubernetes routes traffic to a pod.
      </p>

      <div className="status-row">
        <span className={`badge ${status.tone}`} data-testid="overall-status">
          {status.label}
        </span>
        <span className="muted" data-testid="status-detail">
          {status.detail}
        </span>
      </div>

      <ul className="check-list">
        {DEPENDENCIES.map((dependency) => {
          const healthy = readinessPayload?.checks[dependency];
          const label = healthy === undefined ? "unknown" : healthy ? "healthy" : "unhealthy";
          return (
            <li key={dependency}>
              <span className={`badge ${badgeTone(healthy)}`} data-testid={`check-${dependency}`}>
                {dependency}: {label}
              </span>
              <span className="muted">reported by GET /ready</span>
            </li>
          );
        })}
      </ul>

      {isLoading ? (
        <p className="loading" role="status">
          Checking service status…
        </p>
      ) : null}

      {failureMessage === null ? null : (
        <p className="error-box" role="alert" data-testid="status-error">
          {failureMessage}
        </p>
      )}

      <div className="status-row">
        <button type="button" className="secondary" onClick={refresh} disabled={isLoading}>
          {isLoading ? "Refreshing…" : "Refresh status"}
        </button>
        <span className="muted">
          Last checked: {lastChecked === null ? "not yet" : formatTimestamp(lastChecked)}
        </span>
      </div>

      <p className="muted correlation" data-testid="status-correlation">
        Request correlation: {correlationId ?? "not available"}
      </p>
    </section>
  );
}
