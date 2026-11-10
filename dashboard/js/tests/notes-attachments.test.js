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

function panelWith(rows) {
  const doc = new FakeDocument();
  const panel = doc.add(new FakeElement("section", doc));
  panel.classList.add("hidden");
  const calls = [];
  const http = {
    rows,
    async getJSON(url) {
      calls.push(url);
      return { ok: true, attachments: http.rows };
    },
  };
  const opened = [];
  const view = createNoteAttachments({
    doc,
    http,
    panel,
    win: { open: (u) => opened.push(u) },
  });
  return { doc, panel, view, http, calls, opened };
}

const actions = (panel) => panel.querySelectorAll(".notes-attachment-action");

describe("Notes attachments panel", () => {
  test("shows each PDF with working View, Download and Print controls", async () => {
    const { doc, panel, view, calls } = panelWith([ITEM]);
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
    printButton.click();
    const frame = doc.body.children.find((c) => c.tagName === "IFRAME");
    expect(frame.getAttribute("src")).toBe(attachmentFileURL(DEED, ITEM.id));
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
