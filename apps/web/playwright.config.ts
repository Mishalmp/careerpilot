import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against their own stack so they never touch development data:
//   database  careerpilot_e2e (recreated by apps/api/scripts/prepare_e2e.py)
//   API       http://127.0.0.1:8011  (worker off, hash embedder, no AI key)
//   web       http://localhost:3101  (production build, talks to the API above)
// Run: npm run e2e   (first time: nothing to download, it uses the Chrome installed on this machine)
const WEB = "http://localhost:3101";
const API = "http://127.0.0.1:8011";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/.results",
  fullyParallel: false, // one shared database; tests that need isolation create their own rows
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "e2e/.report" }]],
  use: {
    baseURL: WEB,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chrome", use: { ...devices["Desktop Chrome"], channel: "chrome" } }],
  webServer: [
    {
      // Recreate the E2E database, then serve the API on it (see apps/api/scripts/prepare_e2e.py).
      command: "python -m uv run python scripts/prepare_e2e.py --serve",
      cwd: "../api",
      url: `${API}/readyz`,
      reuseExistingServer: false,
      timeout: 180_000,
    },
    {
      command: "npx next build && npx next start -p 3101",
      url: `${WEB}/login`,
      reuseExistingServer: false,
      timeout: 300_000,
      env: {
        API_ORIGIN: API,
        RUNNER_ORIGINS: "http://localhost:3101,http://127.0.0.1:3101",
      },
    },
  ],
});
