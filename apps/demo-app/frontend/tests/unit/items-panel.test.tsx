/**
 * Component tests for the items inventory panel.
 *
 * The panel is asserted against a small in-memory backend that behaves like the demo API (list, create,
 * delete, correlation headers), so the tests cover the loading, empty, success and failure paths of a
 * real request flow without touching a live service.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ItemsPanel } from "@/components/ItemsPanel";
import type { Item } from "@/lib/api";
import type { FetchMock } from "./support/http";
import {
  FIXED_TIMESTAMP,
  SEEDED_ITEMS,
  SEEDED_ITEM_ACTIVE,
  fetchCall,
  jsonResponse,
  stubFetch,
} from "./support/http";

afterEach(() => {
  vi.unstubAllGlobals();
});

interface ItemBackend {
  items: () => Item[];
  mock: FetchMock;
}

/** Install an in-memory stand-in for the demo API's item endpoints. */
function itemBackend(initial: Item[] = SEEDED_ITEMS): ItemBackend {
  let items = [...initial];

  const mock = stubFetch(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (method === "POST") {
      const body = JSON.parse(String(init?.body)) as { name: string; description?: string };
      const created: Item = {
        id: items.length + 1,
        name: body.name,
        description: body.description ?? null,
        is_active: true,
        created_at: FIXED_TIMESTAMP,
      };
      items = [...items, created];
      return jsonResponse(created, { status: 201, headers: { "x-request-id": "create-corr" } });
    }

    if (method === "DELETE") {
      const id = Number(url.slice(url.lastIndexOf("/") + 1));
      items = items.filter((item) => item.id !== id);
      return new Response(null, { status: 204, headers: { "x-request-id": "delete-corr" } });
    }

    return jsonResponse(items, { headers: { "x-request-id": "list-corr" } });
  });

  return { items: () => items, mock };
}

describe("ItemsPanel", () => {
  it("renders the inventory returned by the API", async () => {
    itemBackend();

    render(<ItemsPanel />);

    expect(await screen.findByText(SEEDED_ITEM_ACTIVE.name)).toBeInTheDocument();
    expect(screen.getByText("paused-item")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
    expect(screen.getByTestId("items-correlation")).toHaveTextContent("list-corr");
  });

  it("shows an empty state when the inventory is empty", async () => {
    itemBackend([]);

    render(<ItemsPanel />);

    expect(await screen.findByText(/No items yet/)).toBeInTheDocument();
  });

  it("reports a failing inventory request", async () => {
    stubFetch(async () => jsonResponse({ detail: "failure_mode=error_rate" }, { status: 503 }));

    render(<ItemsPanel />);

    expect(await screen.findByTestId("items-error")).toHaveTextContent(
      "temporarily unavailable (HTTP 503)",
    );
  });

  it("creates an item, reloads the list and reports the mutation correlation id", async () => {
    itemBackend();
    const user = userEvent.setup();

    render(<ItemsPanel />);
    await screen.findByText(SEEDED_ITEM_ACTIVE.name);

    await user.type(screen.getByLabelText("Name"), "new-item");
    await user.type(screen.getByLabelText("Description"), "created by a test");
    await user.click(screen.getByRole("button", { name: "Create item" }));

    expect(await screen.findByText("new-item")).toBeInTheDocument();
    expect(screen.getByTestId("mutation-note")).toHaveTextContent('Created item "new-item".');
    expect(screen.getByTestId("mutation-note")).toHaveTextContent("create-corr");
    expect(screen.getByLabelText("Name")).toHaveValue("");
  });

  it("posts a trimmed payload and omits an empty description", async () => {
    const backend = itemBackend();
    const user = userEvent.setup();

    render(<ItemsPanel />);
    await screen.findByText(SEEDED_ITEM_ACTIVE.name);

    await user.type(screen.getByLabelText("Name"), "  spaced-name  ");
    await user.type(screen.getByLabelText("Description"), "   ");
    await user.click(screen.getByRole("button", { name: "Create item" }));
    await screen.findByText("spaced-name");

    const postIndex = backend.mock.mock.calls.findIndex((call) => call[1]?.method === "POST");
    expect(JSON.parse(String(fetchCall(backend.mock, postIndex).init.body))).toEqual({
      name: "spaced-name",
    });
  });

  it("rejects an empty name without calling the create endpoint", async () => {
    const backend = itemBackend();
    const user = userEvent.setup();

    render(<ItemsPanel />);
    await screen.findByText(SEEDED_ITEM_ACTIVE.name);

    await user.click(screen.getByRole("button", { name: "Create item" }));

    expect(await screen.findByTestId("form-error")).toHaveTextContent("A name is required.");
    expect(backend.mock.mock.calls.every((call) => call[1]?.method !== "POST")).toBe(true);
  });

  it("deletes an item and reloads the inventory", async () => {
    const backend = itemBackend();
    const user = userEvent.setup();

    render(<ItemsPanel />);
    await screen.findByText(SEEDED_ITEM_ACTIVE.name);

    await user.click(screen.getAllByRole("button", { name: "Delete" })[0]!);

    await waitFor(() => {
      expect(screen.queryByText(SEEDED_ITEM_ACTIVE.name)).not.toBeInTheDocument();
    });
    expect(backend.items()).toHaveLength(1);
    expect(screen.getByTestId("mutation-note")).toHaveTextContent("Deleted item #1.");
    expect(screen.getByTestId("mutation-note")).toHaveTextContent("delete-corr");
  });

  it("reports a failed creation and keeps the typed values", async () => {
    stubFetch(async (_input, init) => {
      if ((init?.method ?? "GET") === "POST") {
        return jsonResponse({ detail: "injected failure" }, { status: 503 });
      }
      return jsonResponse(SEEDED_ITEMS);
    });
    const user = userEvent.setup();

    render(<ItemsPanel />);
    await screen.findByText(SEEDED_ITEM_ACTIVE.name);

    await user.type(screen.getByLabelText("Name"), "rejected-item");
    await user.click(screen.getByRole("button", { name: "Create item" }));

    expect(await screen.findByTestId("form-error")).toHaveTextContent(
      "temporarily unavailable (HTTP 503)",
    );
    expect(screen.getByLabelText("Name")).toHaveValue("rejected-item");
  });
});
