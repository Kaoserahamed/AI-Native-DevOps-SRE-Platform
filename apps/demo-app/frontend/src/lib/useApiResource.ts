"use client";

/**
 * Minimal async-resource hook shared by the demo panels.
 *
 * Responsibilities are deliberately narrow: run a typed API request, expose the loading/error/data
 * triad, keep the request correlation ID, and abort in-flight work when the component unmounts or the
 * resource is reloaded. Callers pass a memoized loader (see `useCallback` in the panels), so the effect
 * only re-runs when the caller's dependencies or an explicit reload change.
 */

import { useCallback, useEffect, useState } from "react";

import type { ApiResult } from "./api";

/** A request function that honours an abort signal. */
export type ResourceLoader<T> = (signal: AbortSignal) => Promise<ApiResult<T>>;

/** State exposed for one API-backed resource. */
export interface ApiResource<T> {
  data: T | null;
  correlationId: string | null;
  /** `null` until a request fails; the raw cause is kept so callers can interpret it. */
  error: unknown;
  isLoading: boolean;
  reload: () => void;
}

/** Load an API resource and expose its loading, error and correlation state. */
export function useApiResource<T>(
  loader: ResourceLoader<T>,
  initialData: T | null = null,
): ApiResource<T> {
  const [data, setData] = useState<T | null>(initialData);
  const [correlationId, setCorrelationId] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [reloadCount, setReloadCount] = useState(0);

  const reload = useCallback(() => {
    setReloadCount((current) => current + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    setIsLoading(true);
    setError(null);

    loader(controller.signal)
      .then((result) => {
        if (!active) {
          return;
        }
        setData(result.data);
        setCorrelationId(result.correlationId);
      })
      .catch((cause: unknown) => {
        if (!active) {
          return;
        }
        setError(cause);
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [loader, reloadCount]);

  return { data, correlationId, error, isLoading, reload };
}
