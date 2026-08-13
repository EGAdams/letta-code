import { describe, expect, test } from "bun:test";
import { InterfacePageRenderer } from "../plans/interface-page.js";
import { Status } from "../plans/interface-spec.js";
import { InterfaceWorkspace } from "../plans/interface-workspace.js";
import { FakeDocument } from "./_fake-dom.js";

/** Records what it was asked to draw; stands in for MermaidView. */
class FakeMermaid {
  constructor() {
    this.rendered = [];
    this.destroyed = 0;
  }
  async render(parent, diagram) {
    this.rendered.push(diagram.title);
    const el = parent._doc
      ? parent._doc.createElement("figure")
      : { tagName: "FIGURE" };
    parent.append(el);
    return el;
  }
  destroyAll() {
    this.destroyed += 1;
  }
}

const specA = {
  id: "alpha",
  name: "Alpha",
  group: "Group one",
  status: Status.FINISHED,
  statusNote: "All good.",
  responsibility: ["Alpha owns one job."],
  contract: { code: "alpha()" },
  implementations: [
    { name: "AlphaImpl", kind: "current", file: "a.js", note: "the real one" },
    { name: "AlphaFuture", kind: "planned" },
    { name: "AlphaOld", kind: "deprecated" },
  ],
  dependencies: { dependsOn: ["Bee"], usedBy: ["Caller"], note: "one-way" },
  developmentStatus: { done: ["it works"], gaps: ["no cancel"] },
  tests: {
    files: [{ path: "js/tests/a.test.js", count: 3, proves: "it works" }],
    untested: ["cancel"],
    next: ["a cancel test"],
  },
  diagrams: [
    { title: "Alpha one", code: "flowchart LR\n A-->B" },
    { title: "Alpha two", code: "flowchart LR\n B-->C" },
  ],
  nextWork: ["build cancel"],
};

const specB = {
  id: "beta",
  name: "Beta",
  group: "Group two",
  status: Status.PLANNED,
  responsibility: ["Beta is not built."],
  diagrams: [{ title: "Beta one", code: "flowchart LR\n X-->Y" }],
  nextWork: ["start it"],
};

function setup({ hash = "" } = {}) {
  const doc = new FakeDocument();
  const nav = doc.createElement("nav");
  nav.id = "nav";
  const content = doc.createElement("main");
  content.id = "content";
  doc.add(nav);
  doc.add(content);
  const win = { location: { hash }, addEventListener: () => {} };
  const mermaid = new FakeMermaid();
  const workspace = new InterfaceWorkspace({
    specs: [specA, specB],
    pageRenderer: new InterfacePageRenderer({ mermaidView: mermaid, doc }),
    mermaidView: mermaid,
    doc,
    win,
  });
  return { doc, nav, content, win, mermaid, workspace };
}

const text = (el) => {
  const parts = [];
  const walk = (node) => {
    if (node.textContent && !node.children?.length)
      parts.push(node.textContent);
    for (const child of node.children || []) walk(child);
  };
  walk(el);
  return parts.join(" | ");
};

describe("InterfaceWorkspace", () => {
  test("builds one nav item per spec, grouped, with a status dot", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    const items = ctx.nav.querySelectorAll(".nav-item");
    expect(items.length).toBe(2);
    expect(ctx.nav.querySelectorAll(".nav-group").length).toBe(2);
    expect(items[0].querySelector(".status-finished")).toBeTruthy();
    expect(items[1].querySelector(".status-planned")).toBeTruthy();
  });

  test("opens the first spec by default and marks it active", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    expect(ctx.workspace.currentId).toBe("alpha");
    expect(
      ctx.nav.querySelectorAll(".nav-item")[0].classList.contains("active"),
    ).toBe(true);
  });

  test("can mount content-only when the dashboard owns navigation", async () => {
    const ctx = setup();
    await ctx.workspace.mount(null, "content");
    expect(ctx.workspace.currentId).toBe("alpha");
    expect(ctx.nav.children.length).toBe(0);
    expect(ctx.content.querySelector(".spec-header")).toBeTruthy();
  });

  test("honours a deep link to a specific interface", async () => {
    const ctx = setup({ hash: "#beta" });
    await ctx.workspace.mount("nav", "content");
    expect(ctx.workspace.currentId).toBe("beta");
  });

  test("falls back to the first spec for an unknown hash", async () => {
    const ctx = setup({ hash: "#nope" });
    await ctx.workspace.mount("nav", "content");
    expect(ctx.workspace.currentId).toBe("alpha");
  });

  test("switching tabs updates the hash and the active item", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    await ctx.workspace.show("beta");
    expect(ctx.win.location.hash).toBe("beta");
    const items = ctx.nav.querySelectorAll(".nav-item");
    expect(items[0].classList.contains("active")).toBe(false);
    expect(items[1].classList.contains("active")).toBe(true);
  });

  test("tears down the previous tab's diagrams before rendering the next", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    const before = ctx.mermaid.destroyed;
    await ctx.workspace.show("beta");
    expect(ctx.mermaid.destroyed).toBe(before + 1);
  });

  test("an unknown id changes nothing", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    expect(await ctx.workspace.show("missing")).toBeNull();
    expect(ctx.workspace.currentId).toBe("alpha");
  });

  test("refuses to build without a page renderer", () => {
    expect(() => new InterfaceWorkspace({ specs: [specA] })).toThrow(
      "page renderer",
    );
  });

  test("rejects invalid spec data at construction", () => {
    expect(
      () =>
        new InterfaceWorkspace({
          specs: [{ id: "bad" }],
          pageRenderer: new InterfacePageRenderer(),
        }),
    ).toThrow("name required");
  });
});

describe("InterfacePageRenderer", () => {
  test("renders every section in the agreed order", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    const headings = ctx.content
      .querySelectorAll(".spec-section")
      .map((s) => s.children[0]?.textContent)
      .filter(Boolean);
    expect(headings).toEqual([
      "1 · Responsibility",
      "2 · Contract",
      "3 · Implementations",
      "4 · Dependencies",
      "5 · Development status",
      "6 · Tests",
      "7 · Next work",
    ]);
  });

  test("status and tests headings appear even on an undocumented interface", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    await ctx.workspace.show("beta");
    const headings = ctx.content
      .querySelectorAll(".spec-section")
      .map((s) => s.children[0]?.textContent)
      .filter(Boolean);
    expect(headings).toContain("5 · Development status");
    expect(headings).toContain("6 · Tests");
  });

  test("shows the status pill and note in the header", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    const pill = ctx.content.querySelector(".pill");
    expect(pill.textContent).toBe("Finished");
    expect(pill.classList.contains("status-finished")).toBe(true);
    expect(ctx.content.querySelector(".spec-status-note").textContent).toBe(
      "All good.",
    );
  });

  test("separates current, planned and deprecated implementations", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    expect(ctx.content.querySelectorAll("tr.impl-current").length).toBe(1);
    expect(ctx.content.querySelectorAll("tr.impl-planned").length).toBe(1);
    expect(ctx.content.querySelectorAll("tr.impl-deprecated").length).toBe(1);
  });

  test("splits done from gaps so status is never a single blob", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    const good = ctx.content.querySelector(".box.good");
    const warn = ctx.content.querySelector(".box.warn");
    expect(text(good)).toContain("it works");
    expect(text(warn)).toContain("no cancel");
  });

  test("says so plainly when an interface has no tests", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    await ctx.workspace.show("beta");
    expect(text(ctx.content)).toContain(
      "No tests exist for this interface yet.",
    );
  });

  test("draws the first diagram high on the page and the rest lower down", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    expect(ctx.mermaid.rendered).toEqual(["Alpha one", "Alpha two"]);
  });

  test("replaces the previous page rather than appending to it", async () => {
    const ctx = setup();
    await ctx.workspace.mount("nav", "content");
    await ctx.workspace.show("beta");
    expect(text(ctx.content)).toContain("Beta is not built.");
    expect(text(ctx.content)).not.toContain("Alpha owns one job.");
  });
});
