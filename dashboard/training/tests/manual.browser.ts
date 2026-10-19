import { expect, test } from "@playwright/test";

test("bookmarks, TOC search, keyboard, history and retained practice progress", async ({
  page,
}) => {
  // This test navigates five times (goto, reload, Next chapter, goBack, goto) and ends with a
  // fullPage screenshot. On this WSL host each of those costs seconds rather than milliseconds,
  // and the whole test has measured 12s alone but 38s with the rest of the suite ahead of it --
  // it failed at the screenshot on one such run. The default 60s is a coin flip under load, so
  // raise it; the per-assertion waits below are still what decides whether the manual works.
  test.setTimeout(180000);
  const failures: string[] = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.goto("/training/index.html#first-session");
  await expect(
    page.getByRole("heading", {
      name: "Your first practice session",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Your first practice session/ }),
  ).toHaveAttribute("aria-current", "page");
  await page.getByLabel("Search this manual").fill("interrupted");
  // Both recovery chapters discuss an interrupted operation: the one that explains it and the
  // session that practises it. Naming them is a stronger assertion than counting them.
  await expect(page.locator("manual-toc a:visible")).toHaveText([
    /Pause, resume, and recover/,
    /Your recovery practice session/,
  ]);
  await page.getByLabel("Search this manual").fill("zzzz-no-result");
  await expect(page.getByText("No chapters match your search.")).toBeVisible();
  await page.getByLabel("Search this manual").fill("");
  await page.getByRole("checkbox").first().check({ force: true });
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "1");
  await page.reload();
  await expect(page.getByRole("checkbox").first()).toBeChecked();
  await page
    .getByRole("button", { name: "Next chapter" })
    .click({ force: true });
  await expect(page).toHaveURL(/#watch-a-run$/);
  await page.goBack();
  await expect(
    page.getByRole("heading", {
      name: "Your first practice session",
      exact: true,
    }),
  ).toBeVisible();
  await page.goto("/training/index.html");
  await expect(
    page.getByRole("heading", {
      name: "Your first practice session",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Reset practice checkmarks" })
    .click({ force: true });
  await expect(page.getByRole("checkbox").first()).not.toBeChecked();
  await page.getByRole("link", { name: /What is coming next/ }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "What is coming next", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator("manual-chapter:not([hidden])")
      .getByText("{to_be_implemented}", { exact: false })
      .first(),
  ).toBeVisible();
  await page.screenshot({
    path: "/tmp/rol-training-manual.png",
    fullPage: true,
  });
  expect(failures).toEqual([]);
});

test("responsive reading, safe copy fallback and no financial operations", async ({
  page,
}) => {
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") writes.push(request.url());
  });
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: async () => {
          throw new Error("denied");
        },
      },
    });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/training/index.html#first-session");
  // This WSL host can starve Chrome's animation-frame stability probe under load.
  await page
    .getByRole("button", { name: "Copy example" })
    .first()
    .click({ force: true });
  await expect(
    page
      .getByText(
        "Copy unavailable. Select the example text and copy it manually.",
      )
      .first(),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
  await page.getByRole("checkbox").first().check({ force: true });
  expect(writes).toEqual([]);
});

test("ROL Finance exposes Training beside the expense tabs", async ({
  page,
}) => {
  // 'commit', not 'domcontentloaded': the dashboard boot opens several long-lived streams, and
  // once Chrome's per-origin connection limit is saturated a still-pending request can keep
  // DOMContentLoaded from firing at all -- this test timed out here while the server was
  // answering the HTML in milliseconds. The startup-loading assertion below is the real wait.
  test.setTimeout(180000);
  await page.goto("/", { waitUntil: "commit" });
  await expect(page.locator("body")).not.toHaveClass(/startup-loading/, {
    timeout: 120000,
  });
  await page
    .locator('[data-nav="main"][data-target="rol-finance"]')
    .click({ force: true });
  await page
    .locator('[data-target="rol-finance-training"]')
    .click({ force: true });
  await expect(page.locator("#rol-finance-training")).toHaveClass(/active/);
  const frame = page.frameLocator("#rol-finance-training iframe");
  await expect(
    frame.getByRole("heading", { name: "ROL Finance training", exact: true }),
  ).toBeVisible();
  await expect(
    page.locator('[data-target="rol-finance-edit-expense"] + button'),
  ).toHaveText("Training");
});
