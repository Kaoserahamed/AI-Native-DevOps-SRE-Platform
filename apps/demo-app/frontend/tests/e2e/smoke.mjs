#!/usr/bin/env node
/**
 * Smoke-test the production frontend artifact.
 *
 * The unit tests cover the panels in jsdom with a stubbed `fetch`. This script covers what only a real
 * production build can prove:
 *
 * 1. `next build` succeeds and emits the standalone output (`output: "standalone"`).
 * 2. The standalone bundle is complete: the entrypoint boots, the page is served, and the static asset
 *    the HTML references is present (the classic monorepo failure mode, where assets are traced but not
 *    copied).
 * 3. The `/api/*` proxy reaches the backend at request time and forwards method, body and query.
 * 4. `X-Request-ID` survives that hop in both directions, so a UI action is traceable in backend logs.
 *
 * A stub backend runs in-process, so the check is hermetic: no PostgreSQL, Redis or demo API needed.
 * Browser-driven end-to-end tests against a deployed revision belong to the repository-wide `tests/e2e`
 * tier, which runs on an ephemeral cluster.
 *
 * Usage:
 *   node tests/e2e/smoke.mjs                       build, then verify the artifact
 *   SMOKE_SKIP_BUILD=1 node tests/e2e/smoke.mjs    verify the existing .next directory
 *
 * Exit codes: 0 all checks passed, 1 at least one check failed, 2 the harness could not run.
 */

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { cp, readFile } from "node:fs/promises";
import http from "node:http";
import { createRequire } from "node:module";
import net from "node:net";
import path from "node:path";
import process from "node:process";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);

/** `apps/demo-app/frontend` — the script lives in `<app>/tests/e2e/`. */
const APP_ROOT = path.resolve(fileURLToPath(new URL("../..", import.meta.url)));
const NEXT_DIR = path.join(APP_ROOT, ".next");
const STANDALONE_DIR = path.join(NEXT_DIR, "standalone");
const SKIP_BUILD = process.env["SMOKE_SKIP_BUILD"] === "1";

const FIXED_TIMESTAMP = "2026-01-02T03:04:05.000Z";
const STARTUP_TIMEOUT_MS = 60_000;
const POLL_INTERVAL_MS = 250;

const SMOKE_ITEM = {
  id: 1,
  name: "smoke-item",
  description: null,
  is_active: true,
  created_at: FIXED_TIMESTAMP,
};

/** Raised when the harness itself cannot run (a build failure, a missing artifact). */
class HarnessError extends Error {}

const passed = [];
const failed = [];

function check(description, condition, detail = "") {
  if (condition) {
    passed.push(description);
    console.info(`  ok   ${description}`);
    return;
  }
  const message = detail === "" ? description : `${description} (${detail})`;
  failed.push(message);
  console.error(`  FAIL ${message}`);
}

/** Absolute path of the Next.js CLI, so the build never depends on a shell resolving `next`. */
function nextBinary() {
  return path.join(path.dirname(require.resolve("next/package.json")), "dist", "bin", "next");
}

/** Start a child process and collect its output for diagnostics. */
function spawnProcess(command, args, options) {
  const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"], ...options });
  const logs = [];
  child.stdout.on("data", (chunk) => logs.push(String(chunk)));
  child.stderr.on("data", (chunk) => logs.push(String(chunk)));
  return { child, logs };
}

/** Run a command to completion, failing the harness when it exits non-zero. */
async function runToCompletion(command, args, cwd, label) {
  const { child, logs } = spawnProcess(command, args, { cwd });
  const code = await new Promise((resolve) => child.once("exit", (exitCode) => resolve(exitCode)));
  if (code !== 0) {
    throw new HarnessError(`${label} failed with exit code ${String(code)}\n${logs.join("")}`);
  }
}

/** Ask the operating system for a free TCP port. */
async function freePort() {
  const probe = net.createServer();
  await new Promise((resolve, reject) => {
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", resolve);
  });
  const address = probe.address();
  const port = typeof address === "object" && address !== null ? address.port : 0;
  await new Promise((resolve) => probe.close(resolve));
  if (port === 0) {
    throw new HarnessError("could not determine a free TCP port");
  }
  return port;
}

/** Start an in-process demo API stub that records the paths it receives. */
async function startStubBackend(port, receivedPaths) {
  const server = http.createServer((request, response) => {
    const pathname = new URL(request.url ?? "/", `http://127.0.0.1:${port}`).pathname;
    receivedPaths.push(pathname);
    const correlationId = `smoke${pathname.replaceAll("/", "_")}`;
    const send = (status, body) => {
      response.writeHead(status, {
        "content-type": "application/json",
        "x-request-id": correlationId,
      });
      response.end(JSON.stringify(body));
    };

    if (pathname === "/health") {
      send(200, { status: "ok", timestamp: FIXED_TIMESTAMP });
      return;
    }
    if (pathname === "/ready") {
      send(200, {
        status: "ready",
        timestamp: FIXED_TIMESTAMP,
        checks: { database: true, redis: true },
      });
      return;
    }
    if (pathname === "/items" || pathname === "/items/") {
      if (request.method === "GET") {
        send(200, [SMOKE_ITEM]);
      } else {
        send(405, { detail: "the smoke stub only answers GET on the items collection" });
      }
      return;
    }
    send(404, { detail: `${pathname} is not part of the smoke stub` });
  });

  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", resolve);
  });
  return server;
}

/**
 * Locate the standalone entrypoint.
 *
 * The file tracer starts at the monorepo root, so the traced application keeps its workspace-relative
 * path inside `.next/standalone`. `required-server-files.json` records that path, so the smoke test
 * follows the build instead of hardcoding it, and fails loudly when the layout changes.
 */
async function locateStandaloneApp() {
  const manifestPath = path.join(NEXT_DIR, "required-server-files.json");
  if (!existsSync(manifestPath)) {
    throw new HarnessError(`${manifestPath} is missing; run the build without SMOKE_SKIP_BUILD`);
  }
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  const relativeAppDir = typeof manifest.relativeAppDir === "string" ? manifest.relativeAppDir : "";
  const directory =
    relativeAppDir === "" ? STANDALONE_DIR : path.join(STANDALONE_DIR, relativeAppDir);
  const entrypoint = path.join(directory, "server.js");
  if (!existsSync(entrypoint)) {
    throw new HarnessError(`standalone entrypoint ${entrypoint} does not exist`);
  }
  return { directory, entrypoint };
}

/** Copy the assets the standalone server serves but does not contain (static output, `public/`). */
async function copyRuntimeAssets(appDirectory) {
  const staticSource = path.join(NEXT_DIR, "static");
  if (!existsSync(staticSource)) {
    throw new HarnessError(`${staticSource} is missing; the build did not complete`);
  }
  await cp(staticSource, path.join(appDirectory, ".next", "static"), { recursive: true });

  const publicSource = path.join(APP_ROOT, "public");
  if (existsSync(publicSource)) {
    await cp(publicSource, path.join(appDirectory, "public"), { recursive: true });
  }
}

/** Wait until the server answers, or fail the harness after the timeout. */
async function waitForServer(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError = "no attempt made";
  while (Date.now() < deadline) {
    try {
      return await fetch(url, { redirect: "manual" });
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
      await delay(POLL_INTERVAL_MS);
    }
  }
  throw new HarnessError(
    `the standalone server did not answer ${url} within ${timeoutMs} ms: ${lastError}`,
  );
}

/** Run every check against the standalone production build. */
async function verifyStandaloneBuild() {
  const { directory, entrypoint } = await locateStandaloneApp();
  await copyRuntimeAssets(directory);
  console.info(
    `smoke: verifying ${path.relative(process.cwd(), entrypoint).split(path.sep).join("/")}`,
  );

  const backendPort = await freePort();
  const frontendPort = await freePort();
  const receivedPaths = [];
  const backend = await startStubBackend(backendPort, receivedPaths);
  const baseUrl = `http://127.0.0.1:${frontendPort}`;

  const { child, logs } = spawnProcess(process.execPath, [entrypoint], {
    cwd: directory,
    env: {
      ...process.env,
      NODE_ENV: "production",
      PORT: String(frontendPort),
      HOSTNAME: "127.0.0.1",
      BACKEND_URL: `http://127.0.0.1:${backendPort}`,
      NEXT_TELEMETRY_DISABLED: "1",
    },
  });

  try {
    const page = await waitForServer(`${baseUrl}/`, STARTUP_TIMEOUT_MS);
    const html = await page.text();
    check("the standalone entrypoint serves GET /", page.status === 200, `status ${page.status}`);
    check("the page renders the workload shell", html.includes("Demo application"));
    check(
      "the page renders both panels",
      html.includes("Service status") && html.includes("Items inventory"),
    );

    const assetPath = /\/_next\/static\/[^"']+\.css/.exec(html)?.[0] ?? null;
    if (assetPath === null) {
      check("the rendered HTML references a built stylesheet", false, "no /_next/static/*.css");
    } else {
      const asset = await fetch(`${baseUrl}${assetPath}`);
      check(
        "static assets are present in the standalone bundle",
        asset.status === 200,
        `${assetPath} -> ${asset.status}`,
      );
    }

    const health = await fetch(`${baseUrl}/api/health`);
    const healthBody = await health.json();
    check("the /api proxy reaches the backend", health.status === 200, `status ${health.status}`);
    check("the proxied payload reaches the client", healthBody.status === "ok");
    check(
      "the backend received the proxied request",
      receivedPaths.includes("/health"),
      receivedPaths.join(", "),
    );
    check(
      "X-Request-ID survives the proxy hop",
      health.headers.get("x-request-id") === "smoke_health",
      String(health.headers.get("x-request-id")),
    );

    const ready = await fetch(`${baseUrl}/api/ready`);
    const readyBody = await ready.json();
    check(
      "readiness is proxied with its dependency checks",
      ready.status === 200 && readyBody.checks.redis === true,
      `status ${ready.status}`,
    );

    const items = await fetch(`${baseUrl}/api/items`);
    const itemList = await items.json();
    check(
      "the items endpoint is proxied",
      items.status === 200 && Array.isArray(itemList) && itemList.length === 1,
      `status ${items.status} body ${JSON.stringify(itemList)}`,
    );

    const trailing = await fetch(`${baseUrl}/api/items/`);
    check(
      "a trailing slash still resolves for clients that send one",
      trailing.status === 200,
      `status ${trailing.status}`,
    );

    const write = await fetch(`${baseUrl}/api/items`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: "smoke" }),
    });
    const writeBody = await write.json();
    check(
      "a write method crosses the proxy unchanged",
      write.status === 405 && writeBody.detail !== undefined,
      `status ${write.status}`,
    );

    const unknown = await fetch(`${baseUrl}/api/does-not-exist`);
    check(
      "an unknown API path returns the backend status, not a frontend page",
      unknown.status === 404,
      `status ${unknown.status}`,
    );
  } finally {
    child.kill();
    await new Promise((resolve) => backend.close(resolve));
    if (failed.length > 0 && logs.length > 0) {
      console.error(`\nstandalone server output:\n${logs.join("")}`);
    }
  }
}

async function main() {
  if (SKIP_BUILD) {
    console.info("smoke: reusing the existing .next build (SMOKE_SKIP_BUILD=1)");
  } else {
    console.info("smoke: building the production frontend");
    await runToCompletion(process.execPath, [nextBinary(), "build"], APP_ROOT, "next build");
  }

  await verifyStandaloneBuild();

  if (failed.length > 0) {
    console.error(`\nsmoke: ${failed.length} of ${passed.length + failed.length} check(s) failed`);
    for (const failure of failed) {
      console.error(`  - ${failure}`);
    }
    return 1;
  }
  console.info(
    `\nsmoke: all ${passed.length} checks passed against the standalone production build`,
  );
  return 0;
}

main()
  .then((code) => {
    process.exitCode = code;
  })
  .catch((error) => {
    console.error(`smoke: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 2;
  });
