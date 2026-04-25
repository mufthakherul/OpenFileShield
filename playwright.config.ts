import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 45_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  reporter: [["list"], ["html", { open: "never" }]],
});
