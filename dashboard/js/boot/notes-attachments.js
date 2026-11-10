// PDF attachments panel for the Notes editor (notes_attachments.py serves the routes).
//
// One row per attachment on the open note: its title, file name, size, pages and the start of its sha256, with
// three controls -- View PDF (the real PDF, inline, in a new tab), Download (the same bytes as a download) and
// Print (the PDF loaded into a hidden same-origin frame and printed from there; if the browser will not print a
// frame, the PDF opens in a new tab so its own Print button is one click away). The list is read from the
// dashboard, never from browser storage, so what it shows is what is stored on disk. Nothing here edits the note.

const LIST = "/api/notes/attachments";
const FILE = "/api/notes/attachment-file";

export function attachmentFileURL(filename, id, { download = false } = {}) {
  const query = new URLSearchParams({ filename, id });
  if (download) query.set("download", "1");
  return `${FILE}?${query}`;
}

function sizeText(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} bytes`;
}

export function createNoteAttachments({ doc, http, panel, win = globalThis }) {
  let current = "";
  let shownKey = null; // null: nothing rendered yet for the open note
  if (!panel)
    return { show: async () => {}, refresh: async () => {}, clear: () => {} };

  const list = doc.createElement("div");
  list.className = "notes-attachments-list";
  const heading = doc.createElement("h4");
  heading.textContent = "Attachments";
  panel.appendChild(heading);
  panel.appendChild(list);

  const link = (label, href, extra = {}) => {
    const a = doc.createElement("a");
    a.className = "am-btn notes-attachment-action";
    a.textContent = label;
    a.setAttribute("href", href);
    for (const [k, v] of Object.entries(extra)) a.setAttribute(k, v);
    return a;
  };

  const print = (url) => {
    const frame = doc.createElement("iframe");
    frame.className = "notes-attachment-print-frame";
    frame.setAttribute("title", "PDF being printed");
    frame.style.position = "fixed";
    frame.style.width = "1px";
    frame.style.height = "1px";
    frame.style.opacity = "0";
    frame.style.border = "0";
    frame.addEventListener("load", () => {
      try {
        frame.contentWindow.focus();
        frame.contentWindow.print();
      } catch (_) {
        win.open?.(url, "_blank", "noopener");
      }
      setTimeout(() => frame.remove(), 60000);
    });
    frame.setAttribute("src", url);
    doc.body?.appendChild(frame);
  };

  const row = (filename, item) => {
    const box = doc.createElement("div");
    box.className = "notes-attachment";
    box.dataset.attachmentId = item.id;
    const name = doc.createElement("strong");
    name.className = "notes-attachment-title";
    name.textContent = item.title || item.filename;
    const meta = doc.createElement("span");
    meta.className = "notes-attachment-meta";
    const pages = item.pages
      ? `, ${item.pages} page${item.pages === 1 ? "" : "s"}`
      : "";
    meta.textContent = ` — ${item.filename} (${sizeText(item.bytes)}${pages}), sha256 ${String(item.sha256).slice(0, 12)}…`;
    const view = link("View PDF", attachmentFileURL(filename, item.id), {
      target: "_blank",
      rel: "noopener",
    });
    const download = link(
      "Download",
      attachmentFileURL(filename, item.id, { download: true }),
      {
        download: item.filename,
      },
    );
    const printButton = doc.createElement("button");
    printButton.type = "button";
    printButton.className = "am-btn notes-attachment-action";
    printButton.textContent = "Print";
    printButton.addEventListener("click", () =>
      print(attachmentFileURL(filename, item.id)),
    );
    box.append(name, meta, view, download, printButton);
    return box;
  };

  const render = (filename, items) => {
    while (list.children.length) list.children[0].remove();
    list.textContent = "";
    if (!items.length) {
      list.textContent = "No PDF attached to this note.";
      return;
    }
    for (const item of items) list.appendChild(row(filename, item));
  };

  const refresh = async () => {
    const filename = current;
    if (!filename) return;
    try {
      const query = new URLSearchParams({
        filename,
        _read: String(Date.now()),
      });
      const result = await http.getJSON(`${LIST}?${query}`);
      if (filename !== current) return;
      const items = result.attachments || [];
      const key = items.map((i) => `${i.id}:${i.sha256}:${i.title}`).join("|");
      if (key === shownKey) return; // unchanged: leave the rows (and any click in progress) alone
      shownKey = key;
      render(filename, items);
    } catch (_) {
      if (filename === current && shownKey === null)
        list.textContent = "Attachments could not be read just now.";
    }
  };

  return {
    show: async (filename) => {
      current = filename || "";
      shownKey = null;
      panel.classList[current ? "remove" : "add"]("hidden");
      list.textContent = "";
      if (current) await refresh();
    },
    refresh,
    clear: () => {
      current = "";
      shownKey = null;
      panel.classList.add("hidden");
    },
  };
}
