// ESLint flat configuration shared by every JavaScript/TypeScript workspace.
//
// Deliberately no type-aware linting: `parserOptions.project` requires a TypeScript project that only
// exists once a workspace has sources, and the frontend phase adds its own type-checked overlay. The
// frontend workspace also declares browser globals itself.
import js from "@eslint/js";
import eslintConfigPrettier from "eslint-config-prettier";
import globals from "globals";
import typescriptEslint from "typescript-eslint";

// Only tracked repository sources are linted. Vendored and generated trees are ignored explicitly:
// ESLint does not ignore dot-directories by default, and the Python virtual environment ships its own
// JavaScript assets (for example the coverage HTML report) that must never be linted.
const sourceGlobs = [
  "*.{js,mjs,cjs,ts,mts,cts,tsx,jsx}",
  "apps/**/*.{js,mjs,cjs,ts,mts,cts,tsx,jsx}",
  "packages/**/*.{js,mjs,cjs,ts,mts,cts,tsx,jsx}",
  "services/**/*.{js,mjs,cjs,ts,mts,cts,tsx,jsx}",
  "scripts/**/*.{js,mjs,cjs,ts,mts,cts,tsx,jsx}",
  "tests/**/*.{js,mjs,cjs,ts,mts,cts,tsx,jsx}",
  ".github/**/*.{js,mjs,cjs}",
];

export default [
  // A global-ignore object must contain only `ignores`, which is why it is kept separate from the
  // `linterOptions` object below. Vendored and generated trees are listed explicitly because ESLint
  // does not ignore dot-directories by default.
  {
    ignores: [
      "**/node_modules/**",
      ".venv/**",
      "**/.venv/**",
      "**/.git/**",
      "**/.next/**",
      "**/dist/**",
      "**/build/**",
      "**/out/**",
      "**/coverage/**",
      "**/htmlcov/**",
      "**/.pytest_cache/**",
      "**/.mypy_cache/**",
      "**/.ruff_cache/**",
      "infra/**",
      "observability/grafana/dashboards/**",
    ],
  },
  {
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
  },
  js.configs.recommended,
  ...typescriptEslint.configs.recommended,
  {
    files: sourceGlobs,
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: {
        ...globals.node,
      },
    },
    rules: {
      eqeqeq: ["error", "always", { null: "ignore" }],
      "no-var": "error",
      "prefer-const": "error",
      "no-console": ["warn", { allow: ["error", "warn", "info"] }],
      "no-param-reassign": "error",
      "no-else-return": "error",
      "object-shorthand": "error",
      "sort-imports": ["error", { ignoreDeclarationSort: true }],
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-non-null-assertion": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  {
    // Test files may use non-null assertions and print diagnostics.
    files: ["**/*.test.{ts,tsx,js,mjs}", "**/tests/**/*.{ts,tsx,js,mjs}"],
    rules: {
      "no-console": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
    },
  },
  // Must stay last: disables rules that conflict with Prettier formatting.
  eslintConfigPrettier,
];
