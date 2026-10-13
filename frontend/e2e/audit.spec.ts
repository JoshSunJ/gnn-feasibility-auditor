import { expect, test } from "@playwright/test";
test("demo, refinement inspection and exact export", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Load demo" }).click();
  await page.getByRole("button", { name: "Run exact audit" }).click();
  await expect(page.getByText("80%", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Graph A", exact: true }),
  ).toHaveValue("cycle-6");
  await page
    .getByRole("combobox", { name: "Graph B", exact: true })
    .selectOption("path-6");
  await page.getByRole("slider", { name: "Refinement round" }).press("End");
  await expect(page.getByText(/1-WL separates this pair/)).toBeVisible();
  await page
    .getByRole("combobox", { name: "Inspect a node in Graph A" })
    .selectOption("0");
  await expect(
    page.getByText("Actual features [1]", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/audit-${test.info().project.name}.png`,
    fullPage: true,
  });
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Certificate JSON ↓" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("report.json");
  const widths = await page.evaluate(() => ({
    body: document.documentElement.scrollWidth,
    viewport: innerWidth,
  }));
  expect(widths.body).toBeLessThanOrEqual(widths.viewport);
});
test("real file upload followed by invalid input never leaves stale results", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Upload training JSON")
    .setInputFiles("../examples/conflicts.json");
  await page.getByRole("button", { name: "Run exact audit" }).click();
  await expect(page.getByText("80%", { exact: true })).toBeVisible();
  await page
    .getByText("Paste or inspect dataset JSON", { exact: true })
    .click();
  await page
    .getByLabel("Original dataset JSON")
    .fill('{"graphs":[],"graphs":[]}');
  await page.getByRole("button", { name: "Run exact audit" }).click();
  await expect(
    page.getByText("duplicate JSON key 'graphs'", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("80%", { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Certificate JSON ↓" }),
  ).toHaveCount(0);
});
