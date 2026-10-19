import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "*.browser.ts",
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: process.env.DASHBOARD_URL || "http://localhost:8765",
    viewport: { width: 1280, height: 900 },
    launchOptions: {
      executablePath: process.env.CHROME_PATH || "/opt/google/chrome/chrome",
      args: [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
      ],
    },
  },
});
