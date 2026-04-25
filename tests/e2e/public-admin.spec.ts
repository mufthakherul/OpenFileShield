import path from "node:path";

import { expect, test } from "@playwright/test";

const publicBase = process.env.PUBLIC_BASE_URL ?? "http://127.0.0.1:8080";
const adminBase = process.env.ADMIN_BASE_URL ?? "http://127.0.0.1:8081";
const adminToken = process.env.ADMIN_TOKEN ?? "change-this-token";

test("public upload page renders and uploads file", async ({ page }) => {
  await page.goto(`${publicBase}/`);
  await expect(page.getByRole("heading", { name: "OpenFileShield" })).toBeVisible();

  await page.getByLabel("Optional name").fill("Playwright User");
  await page.getByLabel("Optional email").fill("playwright@example.com");
  await page.locator("#scan-mode").selectOption("async");

  const filePath = path.resolve(__dirname, "fixtures", "upload-sample.txt");
  await page.locator("#file-input").setInputFiles(filePath);
  await page.getByRole("checkbox", { name: /I consent/i }).check();
  await page.getByRole("button", { name: "Scan and Upload" }).click();

  await expect(page.locator("#result")).toContainText(/upload_status|Rejected/);
});

test("admin dashboard loads with token and external forwarded IP is blocked", async ({ page, request }) => {
  await page.goto(`${adminBase}/`);
  await expect(page.getByRole("heading", { name: "OpenFileShield Admin" })).toBeVisible();

  await page.getByPlaceholder("x-admin-token").fill(adminToken);
  await page.getByRole("button", { name: "Save token" }).click();
  await page.getByRole("button", { name: "Load dashboard" }).click();
  await expect(page.locator("#admin-result")).toContainText(/Loaded|token/i);

  const blocked = await request.get(`${adminBase}/api/stats`, {
    headers: {
      "x-admin-token": adminToken,
      "x-forwarded-for": "8.8.8.8",
    },
  });
  expect(blocked.status()).toBe(403);
});
