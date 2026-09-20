/**
 * Operator-facing descriptions of demo API transport errors.
 *
 * The UI never renders a raw stack trace or an unbounded upstream payload: a dashboard that leaks
 * internals is worse than one that says "unavailable". Every branch therefore returns a short, stable
 * sentence that names the failure class and the HTTP status.
 */

import { ApiError } from "./api";

const FALLBACK_MESSAGE = "The demo API could not be reached and returned no error detail.";

/** Return a one-sentence description of a failed request, safe to display in the UI. */
export function describeRequestError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return "The demo API reported that the requested resource does not exist (HTTP 404).";
    }
    if (error.status === 422) {
      return "The demo API rejected the request payload (HTTP 422).";
    }
    if (error.status === 503) {
      return "The demo API is temporarily unavailable (HTTP 503); a failure mode may be active.";
    }
    if (error.status >= 500) {
      return `The demo API returned a server error (HTTP ${error.status}).`;
    }
    return `The demo API returned an unexpected status (HTTP ${error.status}).`;
  }
  if (error instanceof Error && error.message !== "") {
    return error.message;
  }
  return FALLBACK_MESSAGE;
}
