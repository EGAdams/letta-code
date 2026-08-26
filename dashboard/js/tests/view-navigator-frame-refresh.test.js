// A plan iframe is fetched once, when the dashboard page loads. A tab switch
// only toggles a CSS class, so a dashboard left open all day keeps showing
// whichever revision of a plan it pulled at load time -- which is how the
// Dashboard Refactor plan appeared unchanged after a verified deploy. Frames
// marked data-refresh-on-show must re-fetch every time their tab is opened.
import { describe, expect, test } from "bun:test";
import { createViewNavigator } from "../boot/view-navigator.js";
import { FakeDocument } from "./_fake-dom.js";

const PLAN_SRC = "/notes_plans_handoffs/dashboard_refactor_plan.html";

function setup({ marked = true, src = PLAN_SRC } = {}) {
  const doc = new FakeDocument();

  const view = doc.createElement("section");
  view.id = "plans-dashboard-refactor";
  view.classList.add("view");

  const frame = doc.createElement("iframe");
  frame.classList.add("plan-frame");
  if (marked) frame.dataset.refreshOnShow = "";
  frame.src = src;
  view.appendChild(frame);

  const other = doc.createElement("section");
  other.id = "home";
  other.classList.add("view");

  const nav = { mainContent: doc.createElement("div") };
  return { navigator: createViewNavigator({ doc, nav }), frame };
}

describe("plan frames marked data-refresh-on-show", () => {
  test("re-fetch the first time their tab is opened", () => {
    const { navigator, frame } = setup();

    navigator.activateView("plans-dashboard-refactor");

    expect(frame.src).toMatch(
      /^\/notes_plans_handoffs\/dashboard_refactor_plan\.html\?_t=\d+$/,
    );
  });

  test("get a different url on every show, so nothing is served from cache", () => {
    const { navigator, frame } = setup();

    navigator.activateView("plans-dashboard-refactor");
    const first = frame.src;
    // Date.now() has millisecond resolution; spin until it ticks so the test
    // is measuring the rebuild, not the clock.
    const start = Date.now();
    while (Date.now() === start) {
      /* wait for the next millisecond */
    }
    navigator.activateView("plans-dashboard-refactor");

    expect(frame.src).not.toBe(first);
  });

  test("rebuild from the authored src rather than stacking _t= params", () => {
    const { navigator, frame } = setup();

    for (let i = 0; i < 5; i++)
      navigator.activateView("plans-dashboard-refactor");

    expect(frame.src.match(/_t=/g)).toHaveLength(1);
    expect(frame.src.split("?")[0]).toBe(PLAN_SRC);
  });

  test("keep an existing query string and add to it", () => {
    const { navigator, frame } = setup({ src: "/plan.html?month=jan" });

    navigator.activateView("plans-dashboard-refactor");

    expect(frame.src).toMatch(/^\/plan\.html\?month=jan&_t=\d+$/);
  });

  test("leave unmarked plan frames alone", () => {
    // Most plan frames are not marked, and the ROL Finance report frames have
    // their src assigned by their own controller -- re-setting those would
    // fight it.
    const { navigator, frame } = setup({ marked: false });

    navigator.activateView("plans-dashboard-refactor");

    expect(frame.src).toBe(PLAN_SRC);
  });

  test("do not blow up on a marked frame that has no src yet", () => {
    const { navigator, frame } = setup({ src: "" });

    expect(() =>
      navigator.activateView("plans-dashboard-refactor"),
    ).not.toThrow();
    expect(frame.src).toBe("");
  });
});
