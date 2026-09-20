"use client";

/**
 * Item inventory panel.
 *
 * Every mutation here is a real PostgreSQL write behind the Redis cache, which makes the panel a
 * convenient way to generate traffic — and, with a failure mode enabled, real errors — for the
 * observe → detect → diagnose loop.
 */

import type { FormEvent } from "react";
import { useCallback, useState } from "react";

import type { Item, ItemCreate } from "@/lib/api";
import { createItem, deleteItem, listItems } from "@/lib/api";
import { formatTimestamp } from "@/lib/display";
import { describeRequestError } from "@/lib/errors";
import { useApiResource } from "@/lib/useApiResource";

interface Mutation {
  message: string;
  correlationId: string | null;
}

/** Render the items inventory card with create and delete affordances. */
export function ItemsPanel() {
  const loadItems = useCallback((signal: AbortSignal) => listItems({ signal }), []);
  const items = useApiResource<Item[]>(loadItems, []);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<number | null>(null);
  const [mutation, setMutation] = useState<Mutation | null>(null);

  const reloadItems = items.reload;

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const trimmedName = name.trim();
    if (trimmedName === "") {
      setFormError("A name is required.");
      return;
    }

    setFormError(null);
    setIsSubmitting(true);
    try {
      const payload: ItemCreate = { name: trimmedName };
      const trimmedDescription = description.trim();
      if (trimmedDescription !== "") {
        payload.description = trimmedDescription;
      }
      const result = await createItem(payload);
      setMutation({
        message: `Created item "${result.data.name}".`,
        correlationId: result.correlationId,
      });
      setName("");
      setDescription("");
      reloadItems();
    } catch (cause: unknown) {
      setFormError(describeRequestError(cause));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(itemId: number): Promise<void> {
    setFormError(null);
    setPendingDeleteId(itemId);
    try {
      const result = await deleteItem(itemId);
      setMutation({ message: `Deleted item #${itemId}.`, correlationId: result.correlationId });
      reloadItems();
    } catch (cause: unknown) {
      setFormError(describeRequestError(cause));
    } finally {
      setPendingDeleteId(null);
    }
  }

  const loadedItems = items.data ?? [];

  return (
    <section className="card" aria-labelledby="items-heading" data-testid="items-panel">
      <h2 id="items-heading">Items inventory</h2>
      <p className="muted">
        Reads are cached in Redis for 60 seconds; writes go straight to PostgreSQL and invalidate
        the cache.
      </p>

      <form className="form-grid" onSubmit={handleSubmit} data-testid="item-form">
        <label>
          Name
          <input
            name="name"
            value={name}
            maxLength={120}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label>
          Description
          <textarea
            name="description"
            value={description}
            maxLength={1000}
            rows={2}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Creating…" : "Create item"}
        </button>
      </form>

      {formError !== null ? (
        <p className="error-box" role="alert" data-testid="form-error">
          {formError}
        </p>
      ) : null}

      {!items.isLoading && items.error !== null ? (
        <p className="error-box" role="alert" data-testid="items-error">
          {describeRequestError(items.error)}
        </p>
      ) : null}

      {items.isLoading && loadedItems.length === 0 ? (
        <p className="loading" role="status">
          Loading items…
        </p>
      ) : null}

      {!items.isLoading && items.error === null && loadedItems.length === 0 ? (
        <p className="empty-state">No items yet — create one to generate traffic.</p>
      ) : null}

      <ul className="item-list" data-testid="item-list">
        {loadedItems.map((item) => (
          <li className="item" key={item.id}>
            <div className="item-header">
              <p className="item-name">{item.name}</p>
              <span className={`badge ${item.is_active ? "badge-ok" : "badge-unknown"}`}>
                {item.is_active ? "active" : "inactive"}
              </span>
            </div>
            <p className="item-meta">
              #{item.id} · created {formatTimestamp(item.created_at)}
            </p>
            {item.description === null || item.description === "" ? null : (
              <p className="item-meta">{item.description}</p>
            )}
            <div className="item-actions">
              <button
                type="button"
                className="secondary"
                disabled={pendingDeleteId === item.id}
                onClick={() => {
                  void handleDelete(item.id);
                }}
              >
                {pendingDeleteId === item.id ? "Deleting…" : "Delete"}
              </button>
            </div>
          </li>
        ))}
      </ul>

      {mutation !== null ? (
        <p className="muted mutation-note" data-testid="mutation-note">
          {mutation.message} Request correlation: {mutation.correlationId ?? "not available"}
        </p>
      ) : null}

      <p className="muted correlation" data-testid="items-correlation">
        Latest list correlation: {items.correlationId ?? "not available"}
      </p>
    </section>
  );
}
