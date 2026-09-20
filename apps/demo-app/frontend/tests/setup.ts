/**
 * Vitest setup shared by the frontend test suites.
 *
 * `@testing-library/jest-dom/vitest` registers the DOM assertions (`toHaveTextContent`, …) with Vitest's
 * `expect`, and the explicit `cleanup` keeps rendered trees from leaking between tests even when the
 * automatic cleanup hook is unavailable.
 */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
