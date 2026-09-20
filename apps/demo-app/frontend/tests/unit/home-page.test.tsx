/**
 * Smoke test for the rendered home page.
 *
 * This is the cheapest end-to-end assertion available without a browser: it renders the page component
 * with a stub backend and proves both panels mount, resolve and display their data.
 */

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/page";
import { HEALTH_OK, READINESS_OK, SEEDED_ITEMS, jsonResponse, stubFetch } from "./support/http";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HomePage", () => {
  it("renders both panels against a healthy backend", async () => {
    stubFetch(async (input) => {
      const url = String(input);
      if (url.endsWith("/ready")) {
        return jsonResponse(READINESS_OK);
      }
      if (url.endsWith("/health")) {
        return jsonResponse(HEALTH_OK);
      }
      return jsonResponse(SEEDED_ITEMS);
    });

    render(<HomePage />);

    expect(screen.getByRole("heading", { name: "Service status" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Items inventory" })).toBeInTheDocument();
    expect(await screen.findByTestId("overall-status")).toHaveTextContent("healthy");
    expect(await screen.findByText("seeded-item")).toBeInTheDocument();
  });
});
