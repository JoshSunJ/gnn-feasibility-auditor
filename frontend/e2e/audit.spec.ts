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

test("compact proof mode and class search work without presenting fake refinement rounds", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Load demo" }).click();
  await page
    .getByRole("combobox", { name: "Audit mode" })
    .selectOption("partition");
  await page.getByRole("button", { name: "Run exact audit" }).click();
  await expect(page.getByText("80%", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("slider", { name: "Refinement round" }),
  ).toBeDisabled();
  await expect(
    page.getByText("Compact split certificate; no round trace"),
  ).toBeVisible();
  await page.getByLabel("Find a class or graph").fill("path-6");
  await expect(page.getByText("No classes match these filters.")).toBeVisible();
  await page
    .getByRole("checkbox", { name: "Conflicting classes only" })
    .uncheck();
  await expect(page.getByText("1 matching classes · page 1/1")).toBeVisible();
  await page.getByRole("button", { name: / · 1 graph/ }).click();
  await expect(
    page.getByRole("combobox", { name: "Graph A", exact: true }),
  ).toHaveValue("path-6");
  await page
    .getByRole("combobox", { name: "Audit mode" })
    .selectOption("trace");
  await expect(page.getByText("80%", { exact: true })).toHaveCount(0);
});

test("a rare forced error stays below 100 percent in both online and offline reports", async ({
  page,
}) => {
  await page.goto("/");
  const raw = JSON.stringify({
    schema_version: 1,
    split: "train",
    graph_type: "simple_undirected",
    feature_dtype: "float64",
    feature_dim: 1,
    graphs: Array.from({ length: 2048 }, (_, i) => ({
      id: `sample-${i}`,
      label: i === 2047 ? 1 : 0,
      nodes: [{ id: "0", features: [1] }],
      edges: [],
    })),
  });
  await page
    .getByText("Paste or inspect dataset JSON", { exact: true })
    .click();
  await page.getByLabel("Original dataset JSON").fill(raw);
  await page.getByRole("button", { name: "Run exact audit" }).click();
  await expect(page.getByText("99.95%", { exact: true })).toBeVisible();
  await expect(
    page.getByText("2047 of 2048 labels at most", { exact: true }),
  ).toBeVisible();
  const offline = await page
    .getByRole("link", { name: "Offline report ↗" })
    .getAttribute("href");
  await page.goto(offline!);
  await expect(page.getByText("99.95%", { exact: true })).toBeVisible();
  await expect(
    page.getByText("2047 of 2048 labels at most", { exact: true }),
  ).toBeVisible();
});
