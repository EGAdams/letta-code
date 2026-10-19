import { expect, test } from "@playwright/test";

const state = {
  assignment: "tax_issues",
  environment: "training",
  status: "ready",
  expense_id: 900001,
  category: "Walgreens (RJ)",
  message: "Opened the expense editor.",
  command: null,
  run_ids: ["11111111", "22222222"],
};

test("second lesson reads checkpoint and phases, selects older run, recovers from errors without writes", async ({
  page,
}) => {
  let fail = false;
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET") writes.push(request.url());
  });
  await page.route("**/api/receptionist-work", (route) =>
    route.fulfill({ json: { ok: true, state } }),
  );
  await page.route("**/api/receptionist-work/trace?*", (route) => {
    if (fail)
      return route.fulfill({ status: 503, json: { error: "unavailable" } });
    const id = new URL(route.request().url()).searchParams.get("run");
    return route.fulfill({
      json: {
        ok: true,
        run_id: id,
        events: [
          {
            adw_id: id,
            phase_id: "p1",
            type: "phase_start",
            name: "load_assignment",
            ts: "2026-10-18T15:00:00Z",
            payload: { description: "Restore assignment" },
          },
          {
            adw_id: id,
            phase_id: "p1",
            type: "phase_end",
            name: "load_assignment",
            ts: "2026-10-18T15:00:01Z",
            payload: { status: "success" },
          },
        ],
      },
    });
  });
  await page.goto("/training/index.html#watch-a-run");
  await expect(
    page.getByRole("heading", {
      name: "Your second practice session",
      exact: true,
    }),
  ).toBeVisible();
  const viewer = page.locator("workflow-inspector");
  await viewer
    .getByRole("button", { name: "Refresh evidence" })
    .click({ force: true });
  await expect(viewer.getByText("900001", { exact: true })).toBeVisible();
  await expect(
    viewer.getByText("Walgreens (RJ)", { exact: true }),
  ).toBeVisible();
  await expect(viewer.getByText("Completed", { exact: true })).toBeVisible();
  await expect(
    viewer.getByRole("link", { name: "Open recorded events" }),
  ).toHaveAttribute("href", /22222222$/);
  await viewer.getByLabel("ADW run").selectOption("11111111");
  await expect(
    viewer.getByRole("link", { name: "Open recorded events" }),
  ).toHaveAttribute("href", /11111111$/);
  fail = true;
  await viewer
    .getByRole("button", { name: "Refresh evidence" })
    .click({ force: true });
  await expect(viewer.getByRole("alert")).toContainText("503");
  await expect(
    viewer.getByText("Completed", { exact: true }),
  ).not.toBeVisible();
  fail = false;
  await viewer
    .getByRole("button", { name: "Refresh evidence" })
    .click({ force: true });
  await expect(viewer.getByText("Completed", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false);
  expect(writes).toEqual([]);
});

test("empty and pending work are explicit, and malformed evidence never looks successful", async ({
  page,
}) => {
  let reads = 0;
  let payload: unknown = {
    ok: true,
    state: { ...state, expense_id: null, category: "", run_ids: [] },
  };
  await page.route("**/api/receptionist-work", (route) => {
    reads++;
    return route.fulfill({ json: payload });
  });
  await page.goto("/training/index.html#watch-a-run");
  const viewer = page.locator("workflow-inspector");
  const refresh = viewer.getByRole("button", { name: "Refresh evidence" });
  await expect(refresh).toBeVisible();
  expect(reads).toBe(0);
  await refresh.click({ force: true });
  await expect(
    viewer.getByText("No ADW runs recorded yet", { exact: true }),
  ).toBeVisible();
  await expect(
    viewer.getByText("None selected", { exact: true }),
  ).toBeVisible();
  payload = {
    ok: true,
    state: {
      ...state,
      status: "waiting_browser",
      command: { action: "category" },
      run_ids: [],
    },
  };
  await refresh.click({ force: true });
  await expect(
    viewer.getByText("waiting_browser", { exact: true }),
  ).toBeVisible();
  await expect(viewer.getByText("category", { exact: true })).toBeVisible();
  payload = { ok: true, state: { ...state, expense_id: "wrong type" } };
  await refresh.click({ force: true });
  await expect(viewer.getByRole("alert")).toContainText(
    "invalid workflow evidence",
  );
  await expect(
    viewer.getByText("waiting_browser", { exact: true }),
  ).not.toBeVisible();
});
