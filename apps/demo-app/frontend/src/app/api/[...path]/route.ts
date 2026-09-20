/**
 * Same-origin `/api/*` proxy for the browser-facing demo API.
 *
 * The route only adapts Next.js's request context to {@link forwardToBackend}; the proxy behaviour
 * (base URL resolution, header bounding, correlation IDs, body handling) lives in `src/lib/backendProxy`
 * so it can be unit tested without a Next.js runtime.
 */

import type { NextRequest } from "next/server";

import { forwardToBackend } from "@/lib/backendProxy";

// Proxied requests must never be statically optimised or cached: the answer belongs to the backend.
export const dynamic = "force-dynamic";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

async function handle(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  return forwardToBackend(request, path);
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
