#!/usr/bin/env node
/**
 * Type-check every TypeScript workspace in the repository.
 *
 * The repository root is not itself a TypeScript project: a bare `tsc -p` on a project without inputs
 * fails with TS18002/TS18003, and `tsc --build` on a solution file with no project references fails the
 * same way. This runner therefore discovers each workspace `tsconfig.json` under `apps/`, `packages/`
 * and `services/`, and builds them one by one. When no workspace exists yet it reports that fact and
 * exits successfully, so `npm run typecheck` is a meaningful gate at every phase of the project.
 *
 * Usage: node scripts/typecheck.mjs
 */
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";

const require = createRequire(import.meta.url);

const REPOSITORY_ROOT = path.resolve(import.meta.dirname, "..");
const WORKSPACE_ROOTS = ["apps", "packages", "services"];
const SKIPPED_DIRECTORIES = new Set(["node_modules", "dist", "build", "out", ".next", "coverage"]);

/** Return the sorted list of workspace tsconfig files to build. */
function discoverProjectConfigs() {
  const configs = [];
  for (const workspaceRoot of WORKSPACE_ROOTS) {
    const rootPath = path.join(REPOSITORY_ROOT, workspaceRoot);
    if (!existsSync(rootPath)) {
      continue;
    }
    for (const group of readdirSync(rootPath)) {
      const groupPath = path.join(rootPath, group);
      if (!isDirectory(groupPath) || SKIPPED_DIRECTORIES.has(group)) {
        continue;
      }
      const directConfig = path.join(groupPath, "tsconfig.json");
      if (existsSync(directConfig)) {
        configs.push(directConfig);
        continue;
      }
      for (const child of readdirSync(groupPath)) {
        const childConfig = path.join(groupPath, child, "tsconfig.json");
        if (isDirectory(path.join(groupPath, child)) && existsSync(childConfig)) {
          configs.push(childConfig);
        }
      }
    }
  }
  return configs.sort();
}

/** Return true when the path exists and is a directory. */
function isDirectory(candidate) {
  return existsSync(candidate) && statSync(candidate).isDirectory();
}

const configs = discoverProjectConfigs();
if (configs.length === 0) {
  console.info("typecheck: no TypeScript workspace yet, nothing to type-check.");
  process.exit(0);
}

const tscPath = require.resolve("typescript/bin/tsc");
const failed = [];
for (const config of configs) {
  const relativeConfig = path.relative(REPOSITORY_ROOT, config).split(path.sep).join("/");
  console.info(`typecheck: building ${relativeConfig}`);
  const result = spawnSync(process.execPath, [tscPath, "--build", config, "--pretty", "false"], {
    cwd: REPOSITORY_ROOT,
    stdio: "inherit",
  });
  if (result.status !== 0) {
    failed.push(relativeConfig);
  }
}

if (failed.length > 0) {
  console.error(`typecheck: failed for ${failed.join(", ")}`);
  process.exit(1);
}
console.info(`typecheck: ${configs.length} workspace(s) passed.`);
