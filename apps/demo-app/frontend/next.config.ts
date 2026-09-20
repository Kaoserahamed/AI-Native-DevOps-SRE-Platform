import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

// The frontend is an npm workspace whose `node_modules` are hoisted to the repository root, so the file
// tracer must start there: without this, `output: "standalone"` would omit hoisted dependencies and the
// standalone server would fail to boot.
//
// Consequence of tracing from the monorepo root: the traced application keeps its workspace-relative
// path inside the standalone directory, so the production entrypoint is
// `.next/standalone/apps/demo-app/frontend/server.js`. `tests/e2e/smoke.mjs` and the container build
// both derive that path from `.next/required-server-files.json` (`relativeAppDir`) instead of hardcoding
// it, and the smoke test fails if this layout changes.
const repositoryRoot = fileURLToPath(new URL("../../..", import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  outputFileTracingRoot: repositoryRoot,
  poweredByHeader: false,
};

export default nextConfig;
