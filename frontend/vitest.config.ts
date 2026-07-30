// Vitest configuration for the frontend test suite.
// Uses jsdom to render React components, resolves the @/ and @shared/* path
// aliases (mirroring tsconfig), and loads a setup file that registers
// Testing Library's jest-dom matchers.

import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["tests/**/*.{test,spec}.{ts,tsx}"],
    css: false,
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
      "@shared": fileURLToPath(new URL("../shared", import.meta.url)),
      // Replace Next.js navigation with a jsdom-safe stub for component tests.
      "next/navigation": fileURLToPath(new URL("./tests/stubs/next-navigation.ts", import.meta.url)),
    },
  },
  esbuild: {
    jsx: "automatic",
  },
});
