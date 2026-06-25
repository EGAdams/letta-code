import { describe, expect, test } from "bun:test";
import { DomDocumentPipelineView } from "../implementation/dom-document-pipeline-view.js";
import { FakeElement } from "./_fake-dom.js";

describe("DomDocumentPipelineView", () => {
  test("requires a container", () => {
    expect(() => new DomDocumentPipelineView(null)).toThrow(/container/);
  });

  test("setBusy reveals the box with a processing message", () => {
    const el = new FakeElement("div");
    el.classList.add("hidden");
    new DomDocumentPipelineView(el).setBusy();
    expect(el.classList.contains("hidden")).toBe(false);
    expect(el.innerHTML).toContain("Processing document");
  });

  test("render lists each stage and the Mazda note", () => {
    const el = new FakeElement("div");
    const view = new DomDocumentPipelineView(el);
    view.render({
      ok: true,
      mazda_dispatched: true,
      stages: [
        {
          name: "classify",
          status: "done",
          doc_kind: "receipt",
          confidence: 0.9,
        },
        { name: "parse", status: "done", parsed: { vendor: "Costco" } },
        { name: "investigate", status: "delegated" },
        { name: "categorize", status: "delegated" },
        { name: "store", status: "delegated" },
      ],
    });
    expect(el.innerHTML).toContain("stage-done");
    expect(el.innerHTML).toContain("stage-delegated");
    expect(el.innerHTML).toContain("vendor=Costco");
    expect(el.innerHTML).toContain("background");
  });

  test("renderError shows an escaped failure message", () => {
    const el = new FakeElement("div");
    new DomDocumentPipelineView(el).renderError("<boom>");
    expect(el.innerHTML).toContain("Pipeline failed");
    expect(el.innerHTML).toContain("&lt;boom&gt;");
  });

  test("clear hides and empties the box", () => {
    const el = new FakeElement("div");
    const view = new DomDocumentPipelineView(el);
    view.setBusy();
    view.clear();
    expect(el.classList.contains("hidden")).toBe(true);
    expect(el.innerHTML).toBe("");
  });
});
