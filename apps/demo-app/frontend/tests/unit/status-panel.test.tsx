/**
 * Component tests for the liveness/readiness panel.
 *
 * The panel is asserted through its operator-visible contract: the verdict badge, the per-dependency
 * checks, the loading state, the single error banner and the request correlation id.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StatusPanel } from "@/components/StatusPanel";
import {
  HEALTH_OK,
  READINESS_DEGRADED,
  READINESS_OK,
  jsonResponse,
  stubFetch,
} from "./support/http";

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Route requests to the two probe endpoints, defaulting to healthy responses. */
function stubProbes(
  handlers: { health?: () => Response; readiness?: () => Response } = {},
): ReturnType<typeof stubFetch> {
  return stubFetch(async (input) => {
    if (String(input).endsWith("/ready")) {
      return (handlers.readiness ?? (() => jsonResponse(READINESS_OK)))();
    }
    return (handlers.health ?? (() => jsonResponse(HEALTH_OK)))();
  });
}

describe("StatusPanel", () => {
  it("renders a healthy verdict with the readiness correlation id", async () => {
    stubProbes({
      health: () => jsonResponse(HEALTH_OK, { headers: { "x-request-id": "health-corr" } }),
      readiness: () =>
        jsonResponse(READINESS_OK, { headers: { "x-request-id": "readiness-corr" } }),
    });

    render(<StatusPanel />);

    await waitFor(() => {
      expect(screen.getByTestId("overall-status")).toHaveTextContent("healthy");
    });
    expect(screen.getByTestId("status-detail")).toHaveTextContent(
      "ready (database: healthy, redis: healthy)",
    );
    expect(screen.getByTestId("check-database")).toHaveTextContent("database: healthy");
    expect(screen.getByTestId("check-redis")).toHaveClass("badge-ok");
    expect(screen.getByTestId("status-correlation")).toHaveTextContent("readiness-corr");
    expect(screen.queryByTestId("status-error")).not.toBeInTheDocument();
  });

  it("treats a 503 readiness payload as a degraded result rather than a transport error", async () => {
    stubProbes({
      readiness: () => jsonResponse(READINESS_DEGRADED, { status: 503 }),
    });

    render(<StatusPanel />);

    await waitFor(() => {
      expect(screen.getByTestId("overall-status")).toHaveTextContent("degraded");
    });
    expect(screen.getByTestId("check-database")).toHaveTextContent("database: unhealthy");
    expect(screen.getByTestId("check-database")).toHaveClass("badge-bad");
    expect(screen.getByTestId("check-redis")).toHaveTextContent("redis: healthy");
    expect(screen.queryByTestId("status-error")).not.toBeInTheDocument();
  });

  it("shows a loading state and unknown dependencies while the probes are in flight", () => {
    stubFetch(() => new Promise<Response>(() => {}));

    render(<StatusPanel />);

    expect(screen.getByRole("status")).toHaveTextContent("Checking service status");
    expect(screen.getByTestId("check-database")).toHaveTextContent("database: unknown");
    expect(screen.getByTestId("overall-status")).toHaveTextContent("unknown");
    expect(screen.getByRole("button", { name: "Refreshing…" })).toBeDisabled();
  });

  it("reports an unreachable API once and probes again on refresh", async () => {
    const mock = stubFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    const user = userEvent.setup();

    render(<StatusPanel />);

    expect(await screen.findByTestId("status-error")).toHaveTextContent(
      /Could not reach the demo API/,
    );
    expect(screen.getAllByTestId("status-error")).toHaveLength(1);
    expect(screen.getByTestId("overall-status")).toHaveTextContent("unknown");

    const callsBefore = mock.mock.calls.length;
    await user.click(screen.getByRole("button", { name: "Refresh status" }));

    await waitFor(() => {
      expect(mock.mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });
});
