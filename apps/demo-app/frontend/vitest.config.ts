import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The `@/*` alias mirrors the `paths` mapping in tsconfig.json so component tests import modules the
// same way the application does.
const srcDirectory = fileURLToPath(new URL("./src", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": srcDirectory },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}", "src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "**/*.d.ts"],
      // A real gate, kept just below the measured values so a regression fails the build instead of
      // being silently accepted. `src/app/layout.tsx` is the only shell that stays below these numbers:
      // it is exercised by the Next.js build and the production smoke test rather than by rendering an
      // <html> tree in jsdom.
      thresholds: {
        statements: 85,
        branches: 85,
        functions: 85,
        lines: 85,
      },
    },
  },
});
