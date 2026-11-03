import { describe, expect, test } from "bun:test";
import {
  canCancel,
  renderJobs,
  renderPrinterPage,
  stateText,
  tabClassFor,
} from "../abstract/printer-render.js";

const payload = {
  ok: true,
  enabled: true,
  error: "",
  default: "hp_8120e",
  documents: 2,
  printers: [
    {
      printer_id: "hp_8120e",
      name: "HPI297BEA (HP OfficeJet 8120e series)",
      status: "Normal",
    },
    {
      printer_id: "hp_4100",
      name: "HP063E28 (HP DeskJet 4100 series)",
      status: "Normal",
    },
  ],
  recent: [
    {
      job_id: "d_aaaaaaaaaaaa",
      state: "completed_per_spooler",
      title: "STAR TREK BRIDGE — PRINT TEST",
      printer: "HPI297BEA",
      submitted_at: "2026-11-02T10:00:00-05:00",
      detail: "",
    },
    {
      job_id: "d_bbbbbbbbbbbb",
      state: "submitted_to_spooler",
      title: "<b>x</b>",
      printer: "HP",
      detail: "",
    },
  ],
};

describe("printer render", () => {
  test("never says printed on paper", () => {
    expect(stateText("completed_per_spooler")).toBe("Left the Windows queue");
    const html = renderPrinterPage(payload);
    expect(html).not.toMatch(/printed successfully/i);
    expect(html).toContain("no printer here confirms that paper came out");
  });

  test("marks the default and escapes titles", () => {
    const html = renderPrinterPage(payload);
    expect(html).toContain("default</span>");
    expect(html).toContain("&lt;b&gt;x&lt;/b&gt;");
    expect(html).not.toContain("<b>x</b>");
  });

  test("cancel only for open jobs", () => {
    expect(canCancel({ state: "submitted_to_spooler" })).toBe(true);
    expect(canCancel({ state: "completed_per_spooler" })).toBe(false);
    expect(canCancel({ state: "ambiguous" })).toBe(false);
    const html = renderJobs(payload.recent);
    expect(html.match(/data-prn="cancel"/g)?.length).toBe(1);
  });

  test("no test button while printing is off", () => {
    const html = renderPrinterPage({ ...payload, enabled: false });
    expect(html).not.toContain('data-prn="test"');
    expect(html).toContain("<strong>off</strong>");
  });

  test("errors show, tab colour follows the switch", () => {
    expect(
      renderPrinterPage({ ok: false, error: "boom", printers: [], recent: [] }),
    ).toContain("boom");
    expect(tabClassFor(payload)).toBe("server-up");
    expect(tabClassFor({ ...payload, enabled: false })).toBe("poll-disabled");
    expect(tabClassFor(null)).toBe("poll-disabled");
  });
});
