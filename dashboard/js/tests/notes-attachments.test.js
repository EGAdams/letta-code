import { describe, expect, test } from "bun:test";
import {
  attachmentFileURL,
  createNoteAttachments,
} from "../boot/notes-attachments.js";
import { FakeDocument, FakeElement } from "./_fake-dom.js";

const DEED = "2026-11-03_deed.md";
const ITEM = {
  id: "a-0123456789ab",
  title: "Latest Printable Deed PDF",
  filename: "Personal_Representative_Deed_for_Notary_REVISED.pdf",
  bytes: 48213,
  pages: 3,
  sha256: "f".repeat(64),
};

function fakeStorage() {
  const data = {};
  return {
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => {
      data[k] = String(v);
    },
  };
}

function panelWith(rows, { postJSON, win } = {}) {
  const doc = new FakeDocument();
  const panel = doc.add(new FakeElement("section", doc));
  panel.classList.add("hidden");
  const calls = [];
  const posted = [];
  const http = {
    rows,
    async getJSON(url) {
      calls.push(url);
      return { ok: true, attachments: http.rows };
    },
    async postJSON(url, body, opts) {
      posted.push({ url, body, opts });
      return postJSON ? postJSON(url, body, opts) : { ok: true };
    },
  };
  const opened = [];
  const view = createNoteAttachments({
    doc,
    http,
    panel,
    win: win || { open: (u) => opened.push(u), localStorage: fakeStorage() },
  });
  return { doc, panel, view, http, calls, posted, opened };
}

const actions = (panel) => panel.querySelectorAll(".notes-attachment-action");
const printerField = (panel) =>
  panel.querySelectorAll(".notes-attachment-printer-id")[0];
const printStatus = (panel) =>
  panel.querySelectorAll(".notes-attachment-print-status")[0];

describe("Notes attachments panel", () => {
  test("shows each PDF with working View and Download controls, and a Print button", async () => {
    const { panel, view, calls } = panelWith([ITEM]);
    await view.show(DEED);
    expect(panel.classList.contains("hidden")).toBe(false);
    expect(calls[0]).toContain(
      `/api/notes/attachments?filename=${encodeURIComponent(DEED)}`,
    );
    const title = panel.querySelectorAll(".notes-attachment-title")[0];
    expect(title.textContent).toBe("Latest Printable Deed PDF");
    const [viewLink, downloadLink, printButton] = actions(panel);
    expect(viewLink.textContent).toBe("View PDF");
    expect(viewLink.getAttribute("href")).toBe(
      attachmentFileURL(DEED, ITEM.id),
    );
    expect(viewLink.getAttribute("target")).toBe("_blank");
    expect(downloadLink.getAttribute("href")).toContain("download=1");
    expect(printButton.textContent).toBe("Print");
  });

  test("Print sends the exact attachment to the printer workflow, never a browser print dialog", async () => {
    const { doc, panel, view, posted } = panelWith([ITEM]);
    await view.show(DEED);
    printerField(panel).value = "hpi297bea_hp_officejet_8120e_series";
    const [, , printButton] = actions(panel);
    await printButton.click();
    expect(doc.body.children.find((c) => c.tagName === "IFRAME")).toBe(
      undefined,
    );
    expect(posted).toHaveLength(1);
    expect(posted[0].url).toBe("/api/printer/attachment-print");
    expect(posted[0].body).toEqual({
      filename: DEED,
      attachment: ITEM.id,
      printer_id: "hpi297bea_hp_officejet_8120e_series",
      confirm: true,
    });
    expect(printStatus(panel).textContent).toContain("printer workflow");
  });

  test("Print refuses to send without a printer id, and remembers one across panels", async () => {
    const storage = fakeStorage();
    const { panel, view, posted } = panelWith([ITEM], {
      win: { localStorage: storage },
    });
    await view.show(DEED);
    const [, , printButton] = actions(panel);
    await printButton.click();
    expect(posted).toHaveLength(0);
    expect(printStatus(panel).textContent).toContain("Enter a printer id");

    printerField(panel).value = "hpi297bea_hp_officejet_8120e_series";
    printerField(panel).dispatch("change", {});
    const again = panelWith([ITEM], { win: { localStorage: storage } });
    await again.view.show(DEED);
    expect(printerField(again.panel).value).toBe(
      "hpi297bea_hp_officejet_8120e_series",
    );
  });

  test("a backend refusal is shown next to the row, not thrown", async () => {
    const { panel, view, posted } = panelWith([ITEM], {
      postJSON: () => ({ ok: false, message: "Printing is switched off" }),
    });
    await view.show(DEED);
    printerField(panel).value = "hpi297bea_hp_officejet_8120e_series";
    const [, , printButton] = actions(panel);
    await printButton.click();
    expect(posted).toHaveLength(1);
    expect(printStatus(panel).textContent).toBe(
      "Not sent: Printing is switched off",
    );
    expect(printButton.disabled).toBe(false);
  });

  test("says so when a note has no PDF, and hides for a new note", async () => {
    const { panel, view } = panelWith([]);
    await view.show(DEED);
    expect(
      panel.querySelectorAll(".notes-attachments-list")[0].textContent,
    ).toBe("No PDF attached to this note.");
    await view.show("");
    expect(panel.classList.contains("hidden")).toBe(true);
  });

  test("a refresh picks up a PDF an agent just attached, and leaves unchanged rows alone", async () => {
    const { panel, view, http } = panelWith([]);
    await view.show(DEED);
    http.rows = [ITEM];
    await view.refresh();
    const first = panel.querySelectorAll(".notes-attachment")[0];
    expect(first.dataset.attachmentId).toBe(ITEM.id);
    await view.refresh();
    expect(panel.querySelectorAll(".notes-attachment")[0]).toBe(first);
  });

  test("the file URL names the note and the attachment, and nothing else", () => {
    expect(
      attachmentFileURL("a b.md", "a-0123456789ab", { download: true }),
    ).toBe(
      "/api/notes/attachment-file?filename=a+b.md&id=a-0123456789ab&download=1",
    );
  });
});
