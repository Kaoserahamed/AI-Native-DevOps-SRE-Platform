/**
 * Test for the application shell.
 *
 * `layout.tsx` renders an `<html>` tree, which jsdom cannot nest inside a container, so the shell is
 * pinned through its exported metadata instead of being rendered. That is still a real contract: the
 * document title and description are what an operator sees in a browser tab during an incident.
 */

import { describe, expect, it } from "vitest";

import { metadata } from "@/app/layout";

describe("application shell metadata", () => {
  it("titles the document with the demo workload name", () => {
    expect(metadata.title).toBe("Demo App — AI-Native DevOps/SRE Platform");
  });

  it("describes the workload as the platform's observable target", () => {
    expect(String(metadata.description)).toContain("Observable demo workload");
  });
});
