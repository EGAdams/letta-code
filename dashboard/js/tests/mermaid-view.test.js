import { describe, expect, test } from "bun:test";
import { MermaidView } from "../plans/mermaid-view.js";
import { FakeDocument } from "./_fake-dom.js";

class FakeMermaidLib {
  constructor({ fail = false } = {}) {
    this.fail = fail;
    this.config = null;
    this.rendered = [];
  }
  initialize(config) {
    this.config = config;
  }
  async render(id, code) {
    this.rendered.push({ id, code });
    if (this.fail) throw new Error("Syntax error in text");
    return { svg: "<svg></svg>" };
  }
}

function fakePanZoom() {
  const calls = [];
  const instances = [];
  const fn = (svg, options) => {
    const pz = {
      svg,
      options,
      zoomIn: () => calls.push("zoomIn"),
      zoomOut: () => calls.push("zoomOut"),
      fit: () => calls.push("fit"),
      center: () => calls.push("center"),
      reset: () => calls.push("reset"),
      resize: () => calls.push("resize"),
      destroy: () => calls.push("destroy"),
    };
    instances.push(pz);
    return pz;
  };
  fn.calls = calls;
  fn.instances = instances;
  return fn;
}

function setup({ fail = false, withPanZoom = true, mermaid = null } = {}) {
  const doc = new FakeDocument();
  doc.body = { offsetWidth: 1200 };
  const parent = doc.createElement("div");
  doc.add(parent);
  const listeners = [];
  const win = {
    setTimeout: (fn) => fn(),
    addEventListener: (type, fn) => listeners.push({ type, fn }),
    removeEventListener: (type, fn) => {
      const i = listeners.findIndex((l) => l.type === type && l.fn === fn);
      if (i >= 0) listeners.splice(i, 1);
    },
  };
  mermaid ||= new FakeMermaidLib({ fail });
  const panZoom = withPanZoom ? fakePanZoom() : null;
  const view = new MermaidView({ mermaid, svgPanZoom: panZoom, doc, win });
  return { doc, parent, view, mermaid, panZoom, listeners };
}

// The FakeDocument does not parse innerHTML into children, so give the wrapper
// the <svg> the real Mermaid output would have produced.
const stubSvg = (doc, wrap) => {
  const svg = doc.createElement("svg");
  svg.setAttribute = () => {};
  svg.removeAttribute = () => {};
  wrap.append(svg);
  return svg;
};

describe("MermaidView", () => {
  test("initializes with startOnLoad off and sequence wrapping on", () => {
    const ctx = setup();
    expect(ctx.mermaid.config.startOnLoad).toBe(false);
    expect(ctx.mermaid.config.sequence.wrap).toBe(true);
  });

  test("renders a diagram into a bounded wrapper with a title and caption", async () => {
    const ctx = setup();
    await ctx.view.render(ctx.parent, {
      title: "Flow",
      caption: "How it flows",
      code: "flowchart LR\n A-->B",
    });
    const figure = ctx.parent.querySelector(".diagram");
    expect(figure.querySelector(".diagram-title").textContent).toBe("Flow");
    expect(figure.querySelector(".diagram-caption").textContent).toBe(
      "How it flows",
    );
    expect(figure.querySelector(".mermaid-wrap")).toBeTruthy();
    expect(ctx.mermaid.rendered[0].code).toContain("flowchart LR");
  });

  test("gives every diagram a unique id so re-rendering a tab cannot collide", async () => {
    const ctx = setup();
    await ctx.view.render(ctx.parent, { code: "flowchart LR\n A-->B" });
    await ctx.view.render(ctx.parent, { code: "flowchart LR\n C-->D" });
    const [first, second] = ctx.mermaid.rendered;
    expect(first.id).not.toBe(second.id);
  });

  test("offers zoom in, zoom out, fit and reset controls", async () => {
    const ctx = setup();
    await ctx.view.render(ctx.parent, { code: "flowchart LR\n A-->B" });
    const wrap = ctx.parent.querySelector(".mermaid-wrap");
    stubSvg(ctx.doc, wrap);
    const labels = wrap
      .querySelectorAll(".mermaid-btn")
      .map((b) => b.textContent);
    expect(labels).toEqual(["−", "+", "Fit", "Reset"]);
  });

  test("the control buttons drive the pan/zoom instance", async () => {
    const ctx = setup();
    // Render, then attach a pan/zoom by hand against a stubbed <svg>, because
    // the fake DOM does not build children from innerHTML.
    await ctx.view.render(ctx.parent, { code: "flowchart LR\n A-->B" });
    const wrap = ctx.parent.querySelector(".mermaid-wrap");
    stubSvg(ctx.doc, wrap);
    ctx.view._attachPanZoom(wrap);
    const buttons = wrap.querySelectorAll(".mermaid-btn");
    buttons[0].click();
    buttons[1].click();
    buttons[2].click();
    buttons[3].click();
    expect(ctx.panZoom.calls).toContain("zoomOut");
    expect(ctx.panZoom.calls).toContain("zoomIn");
    expect(ctx.panZoom.calls).toContain("fit");
    expect(ctx.panZoom.calls).toContain("reset");
  });

  test("enables wheel zoom and drag pan, scoped so the page still scrolls", async () => {
    const ctx = setup();
    await ctx.view.render(ctx.parent, { code: "flowchart LR\n A-->B" });
    const wrap = ctx.parent.querySelector(".mermaid-wrap");
    stubSvg(ctx.doc, wrap);
    ctx.view._attachPanZoom(wrap);
    const { options } = ctx.panZoom.instances[0];
    expect(options.mouseWheelZoomEnabled).toBe(true);
    expect(options.panEnabled).toBe(true);
    expect(options.preventMouseEventsDefault).toBe(true);
    expect(options.fit).toBe(true);
    expect(options.maxZoom).toBeGreaterThan(1);
  });

  test("a broken diagram shows the error and its source instead of breaking the tab", async () => {
    const ctx = setup({ fail: true });
    const figure = await ctx.view.render(ctx.parent, {
      code: "flowchart LR\n A--",
    });
    const wrap = figure.querySelector(".mermaid-wrap");
    expect(wrap.classList.contains("mermaid-failed")).toBe(true);
    const error = figure.querySelector(".mermaid-error");
    expect(error.textContent).toContain("Syntax error in text");
    expect(error.textContent).toContain("flowchart LR");
  });

  test("destroyAll releases pan/zoom instances and their resize listeners", async () => {
    const ctx = setup();
    await ctx.view.render(ctx.parent, { code: "flowchart LR\n A-->B" });
    const wrap = ctx.parent.querySelector(".mermaid-wrap");
    stubSvg(ctx.doc, wrap);
    ctx.view._attachPanZoom(wrap);
    expect(ctx.listeners.length).toBe(1);
    ctx.view.destroyAll();
    expect(ctx.panZoom.calls).toContain("destroy");
    expect(ctx.listeners.length).toBe(0);
  });

  test("render waits for layout before asking mermaid to draw", async () => {
    const ctx = setup();
    ctx.doc.body = { offsetWidth: 0 };
    let ticks = 0;
    ctx.view._win.setTimeout = (fn) => {
      ticks += 1;
      // Layout arrives on the third poll, as it would when the tab is opened.
      if (ticks === 3) ctx.doc.body.offsetWidth = 1200;
      fn();
    };
    await ctx.view.render(ctx.parent, { code: "flowchart LR\n A-->B" });
    expect(ticks).toBeGreaterThanOrEqual(3);
    expect(ctx.mermaid.rendered.length).toBe(1);
  });

  test("the visibility wait is memoized, so later diagrams do not re-poll", async () => {
    const ctx = setup();
    const first = ctx.view.whenVisible();
    expect(ctx.view.whenVisible()).toBe(first);
  });

  test("whenVisible never gives up while the document remains hidden", async () => {
    const ctx = setup();
    ctx.doc.body = { offsetWidth: 0 };
    const polls = [];
    ctx.view._win.setTimeout = (fn) => polls.push(fn);
    let resolved = false;
    const pending = ctx.view.whenVisible().then(() => {
      resolved = true;
    });
    expect(polls.length).toBe(1);
    polls.shift()();
    await Promise.resolve();
    expect(resolved).toBe(false);
    expect(polls.length).toBe(1);
    ctx.doc.body.offsetWidth = 1200;
    polls.shift()();
    await pending;
    expect(resolved).toBe(true);
  });

  test("serializes Mermaid calls when two tabs render at once", async () => {
    let releaseFirst;
    class ConcurrencySensitiveMermaid extends FakeMermaidLib {
      constructor() {
        super();
        this.active = 0;
      }
      async render(id, code) {
        this.rendered.push({ id, code });
        this.active += 1;
        if (this.active > 1) throw new Error("Syntax error in text");
        if (this.rendered.length === 1)
          await new Promise((resolve) => {
            releaseFirst = resolve;
          });
        this.active -= 1;
        return { svg: "<svg></svg>" };
      }
    }

    const mermaid = new ConcurrencySensitiveMermaid();
    const ctx = setup({ mermaid });
    const first = ctx.view.render(ctx.parent, {
      code: "flowchart LR\n A-->B",
    });
    while (!releaseFirst) await Promise.resolve();
    const second = ctx.view.render(ctx.parent, {
      code: "flowchart LR\n C-->D",
    });
    await Promise.resolve();
    expect(mermaid.rendered.length).toBe(1);
    releaseFirst();
    const figures = await Promise.all([first, second]);
    expect(mermaid.rendered.length).toBe(2);
    expect(
      figures.some((figure) =>
        figure
          .querySelector(".mermaid-wrap")
          .classList.contains("mermaid-failed"),
      ),
    ).toBe(false);
  });

  test("renders without a pan/zoom library rather than throwing", async () => {
    const ctx = setup({ withPanZoom: false });
    const figure = await ctx.view.render(ctx.parent, {
      code: "flowchart LR\n A-->B",
    });
    expect(figure.querySelector(".mermaid-wrap")).toBeTruthy();
  });

  test("refuses to build without the mermaid library", () => {
    expect(() => new MermaidView({})).toThrow("mermaid");
  });
});
