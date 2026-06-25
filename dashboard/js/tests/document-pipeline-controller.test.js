import { describe, expect, test } from "bun:test";
import {
  buildProcessDocumentRequest,
  DocumentPipelineController,
  describePipelineStage,
  summarizeParsed,
} from "../implementation/document-pipeline-controller.js";

// Fake HttpClient that records postJSON calls and returns a scripted result.
const fakeHttp = (result) => {
  const calls = [];
  return {
    calls,
    postJSON: async (url, body) => {
      calls.push({ url, body });
      if (result instanceof Error) throw result;
      return result;
    },
  };
};

// Recording DocumentPipelineView double.
const fakeView = () => {
  const events = [];
  return {
    events,
    setBusy: () => events.push({ type: "busy" }),
    render: (r) => events.push({ type: "render", result: r }),
    renderError: (m) => events.push({ type: "error", message: m }),
    clear: () => events.push({ type: "clear" }),
  };
};

describe("buildProcessDocumentRequest", () => {
  test("builds the /api/process-document payload", () => {
    expect(buildProcessDocumentRequest("window")).toEqual({
      url: "/api/process-document",
      body: { scanner: "window" },
    });
  });

  test("requires a scanner", () => {
    expect(() => buildProcessDocumentRequest("")).toThrow(/requires/);
  });
});

describe("summarizeParsed", () => {
  test("compacts known fields", () => {
    expect(
      summarizeParsed({ vendor: "Costco", total: "84.12", date: "2025-01-03" }),
    ).toBe("vendor=Costco · total=84.12 · date=2025-01-03");
  });

  test("counts line items", () => {
    expect(summarizeParsed({ items: [1, 2, 3] })).toBe("3 items");
  });

  test("falls back for an unrecognized object", () => {
    expect(summarizeParsed({ foo: "bar" })).toBe("structured data extracted");
  });

  test("empty for non-objects", () => {
    expect(summarizeParsed(null)).toBe("");
    expect(summarizeParsed("x")).toBe("");
  });
});

describe("describePipelineStage", () => {
  test("classify done shows kind/vendor/confidence/method/action", () => {
    const d = describePipelineStage({
      name: "classify",
      status: "done",
      doc_kind: "receipt",
      vendor: "Costco",
      confidence: 0.94,
      method: "rule_based",
      recommended_action: "auto",
    });
    expect(d).toEqual({
      name: "classify",
      status: "done",
      summary: "receipt · vendor=Costco · 94% · rule_based · → auto",
    });
  });

  test("parse done summarizes the parsed payload", () => {
    const d = describePipelineStage({
      name: "parse",
      status: "done",
      parsed: { vendor: "Costco", total: "84.12" },
    });
    expect(d.summary).toBe("vendor=Costco · total=84.12");
  });

  test("parse skipped says no structured fields", () => {
    expect(
      describePipelineStage({ name: "parse", status: "skipped" }).summary,
    ).toBe("no structured fields");
  });

  test("delegated stage notes Mazda", () => {
    expect(
      describePipelineStage({ name: "categorize", status: "delegated" })
        .summary,
    ).toBe("delegated to Mazda");
  });

  test("pending stage", () => {
    expect(
      describePipelineStage({ name: "store", status: "pending" }).summary,
    ).toBe("pending");
  });

  test("missing fields default safely", () => {
    expect(describePipelineStage(undefined)).toEqual({
      name: "stage",
      status: "pending",
      summary: "pending",
    });
  });
});

describe("DocumentPipelineController (Command)", () => {
  test("validates injected ports", () => {
    expect(() => new DocumentPipelineController({})).toThrow(/http/);
    expect(
      () => new DocumentPipelineController({ http: { postJSON() {} } }),
    ).toThrow(/view/);
  });

  test("process() posts then renders the result", async () => {
    const http = fakeHttp({ ok: true, stages: [], mazda_dispatched: true });
    const view = fakeView();
    const c = new DocumentPipelineController({ http, view });

    const res = await c.process("freezer");

    expect(http.calls).toEqual([
      { url: "/api/process-document", body: { scanner: "freezer" } },
    ]);
    expect(view.events.map((e) => e.type)).toEqual(["busy", "render"]);
    expect(res.ok).toBe(true);
  });

  test("process() routes a transport error to the view without throwing", async () => {
    const http = fakeHttp(new Error("HTTP 502"));
    const view = fakeView();
    const c = new DocumentPipelineController({ http, view });

    const res = await c.process("window");

    expect(view.events.map((e) => e.type)).toEqual(["busy", "error"]);
    expect(res).toEqual({ ok: false, error: "HTTP 502" });
  });

  test("process() ignores concurrent calls while one is in flight", async () => {
    let release;
    const gate = new Promise((r) => {
      release = r;
    });
    const http = {
      calls: [],
      postJSON: async (url, body) => {
        http.calls.push({ url, body });
        await gate;
        return { ok: true, stages: [] };
      },
    };
    const view = fakeView();
    const c = new DocumentPipelineController({ http, view });

    const first = c.process("window");
    const second = await c.process("window"); // rejected while first in flight
    expect(second).toEqual({ ok: false, error: "already processing" });
    release();
    await first;
    expect(http.calls.length).toBe(1);
  });
});
