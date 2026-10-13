import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:8000", trace: "retain-on-failure" },
  reporter: "list",
  webServer: {
    // Ten audit submissions across the desktop/mobile suite exceed the
    // default eight retained slots; isolate that fixture from retention tests.
    env: { AUDITOR_MAX_RETAINED: "32" },
    command:
      "cd .. && python -m uvicorn gnn_auditor.service.app:app --host 127.0.0.1 --port 8000 --no-access-log",
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: false,
  },
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
    {
      name: "mobile",
      use: { browserName: "chromium", viewport: { width: 390, height: 844 } },
    },
  ],
});
