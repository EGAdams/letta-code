import { expect, test } from "@playwright/test";

test("copy success uses the injected clipboard without sending the example", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: async (text: string) => {
          document.documentElement.dataset.copied = text;
        },
      },
    });
  });
  await page.goto("/training/index.html#first-session");
  await page
    .getByRole("button", { name: "Copy example" })
    .first()
    .click({ force: true });
  await expect(page.locator("html")).toHaveAttribute(
    "data-copied",
    "What can you help me do with tax issues?",
  );
  await expect(
    page
      .getByText(
        "Copied. Paste this into Toyota’s conversation when you are ready.",
      )
      .first(),
  ).toBeVisible();
});

test("blocked storage is reported while the checklist and navigation still work", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new Error("blocked");
      },
    });
  });
  await page.goto("/training/index.html#first-session");
  await expect(
    page.getByText(
      "Browser storage is unavailable. Progress lasts until this page closes.",
    ),
  ).toBeVisible();
  await page.getByRole("checkbox").first().check({ force: true });
  await expect(page.getByRole("progressbar")).toHaveAttribute("value", "1");
});

test("component attributes remain literal and react to later updates", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/training/index.html#first-session");
  await expect(
    page.getByRole("heading", {
      name: "Your first practice session",
      exact: true,
    }),
  ).toBeVisible();
  await page.evaluate(async () => {
    const example = document.createElement("command-example");
    example.id = "standalone-example";
    example.setAttribute("example", "<script>window.bad = true</script>");
    const ready = new Promise<void>((resolve) =>
      example.addEventListener("ready", () => resolve(), { once: true }),
    );
    document.body.append(example);
    await ready;
  });
  await expect(page.locator("#standalone-example code")).toHaveText(
    "<script>window.bad = true</script>",
  );
  await page
    .locator("#standalone-example")
    .evaluate((element) => element.setAttribute("example", "Updated example"));
  await expect(page.locator("#standalone-example code")).toHaveText(
    "Updated example",
  );
  expect(errors).toEqual([]);
});

test("removing and reconnecting the manual restores its history subscription", async ({
  page,
}) => {
  await page.goto("/training/index.html#first-session");
  await expect(
    page.getByRole("heading", {
      name: "Your first practice session",
      exact: true,
    }),
  ).toBeVisible();
  await page.evaluate(() => {
    const manual = document.querySelector("training-manual")!;
    manual.remove();
    document.body.append(manual);
    location.hash = "recovery";
  });
  await expect(
    page.getByRole("heading", {
      name: "Pause, resume, and recover",
      exact: true,
    }),
  ).toBeVisible();
});

test("a component removed before lazy loading can be reattached safely", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/training/index.html");
  await expect(
    page.getByRole("heading", { name: "ROL Finance training", exact: true }),
  ).toBeVisible();
  await page.evaluate(async () => {
    const element = document.createElement("training-callout");
    element.id = "delayed-callout";
    element.setAttribute("heading", "Retained after lazy load");
    element.setAttribute("text", "Still here");
    const ready = new Promise<void>((resolve) =>
      element.addEventListener("ready", () => resolve(), { once: true }),
    );
    document.body.append(element);
    element.remove();
    await ready;
    document.body.append(element);
  });
  await expect(
    page.locator("#delayed-callout").getByRole("heading"),
  ).toHaveText("Retained after lazy load");
  expect(errors).toEqual([]);
});
