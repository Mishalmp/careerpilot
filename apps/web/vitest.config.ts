import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  // Playwright specs live in e2e/ and run with `npm run e2e`, not here.
  test: { exclude: ["e2e/**", "node_modules/**", ".next/**"] },
});
