import { describe, expect, test } from "bun:test";
import { createNotes } from "../boot/notes.js";
import { FakeDocument, FakeElement } from "./_fake-dom.js";

const IDS = [
  "notes-landing",
  "notes-editor",
  "notes-editor-title",
  "notes-editor-name",
  "notes-editor-text",
  "notes-editor-save",
  "notes-editor-back",
  "notes-editor-status",
];

/** A fake server holding notes in memory, answering like the real routes. */
function fakeServer(initial = {}) {
  const files = { ...initial };
  const calls = [];
  const http = {
    fail: null,
    async getJSON(url) {
      calls.push(["GET", url]);
      const name = new URL(url, "http://x").searchParams.get("filename");
      if (name) {
        if (!(name in files)) throw new Error("HTTP 404 — Note not found");
        return { ok: true, filename: name, note: files[name] };
      }
      return { ok: true, notes: Object.keys(files).sort().reverse() };
    },
    async postJSON(url, body) {
      calls.push(["POST", url, body]);
      if (http.fail) throw new Error(http.fail);
      if (url === "/api/note-save") {
        if (!body.note.trim()) return { ok: false, error: "Nothing to save." };
        let name = `2026-11-03_${body.filename.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.md`;
        for (let n = 2; name in files; n++)
          name = name.replace(/(-\d+)?\.md$/, `-${n}.md`);
        files[name] = body.note;
        return { ok: true, filename: name };
      }
      if (url === "/api/note-write") {
        if (!(body.filename in files))
          throw new Error("HTTP 404 — Note not found");
        files[body.filename] = body.note;
        return { ok: true, filename: body.filename };
      }
      throw new Error("HTTP 404");
    },
  };
  return { files, calls, http };
}

function page(server) {
  const doc = new FakeDocument();
  const el = {};
  for (const id of IDS) {
    const tag = id.endsWith("-text")
      ? "textarea"
      : id.endsWith("-name")
        ? "input"
        : "div";
    el[id] = doc.add(new FakeElement(tag, doc));
    el[id].id = id;
  }
  el["notes-editor"].classList.add("hidden");
  createNotes({ doc, http: server.http });
  return { doc, el };
}

const settle = () => new Promise((r) => setTimeout(r, 0));
const buttons = (el) => el["notes-landing"].children || [];
const button = (el, label) => buttons(el).find((b) => b.textContent === label);

describe("Notes page", () => {
  test("a new note saves from the name box, without a browser prompt", async () => {
    const server = fakeServer({ "2026-11-01_old.md": "keep me\n" });
    const prompt = globalThis.prompt;
    globalThis.prompt = () => {
      throw new Error("prompt() must not be needed");
    };
    try {
      const { el } = page(server);
      await settle();
      button(el, "New note").click();
      el["notes-editor-name"].value = "Deed draft";
      el["notes-editor-text"].value = "first version";
      el["notes-editor-save"].click();
      await settle();
      expect(server.files["2026-11-03_deed-draft.md"]).toBe("first version");
      expect(el["notes-editor-status"].textContent).toContain(
        "Saved 2026-11-03_deed-draft.md",
      );
      expect(server.files["2026-11-01_old.md"]).toBe("keep me\n");
    } finally {
      globalThis.prompt = prompt;
    }
  });

  test("saving again after a first save updates that note, not a copy", async () => {
    const server = fakeServer();
    const { el } = page(server);
    await settle();
    button(el, "New note").click();
    el["notes-editor-name"].value = "deed";
    el["notes-editor-text"].value = "v1";
    el["notes-editor-save"].click();
    await settle();
    el["notes-editor-text"].value = "v2";
    el["notes-editor-save"].click();
    await settle();
    expect(Object.keys(server.files)).toEqual(["2026-11-03_deed.md"]);
    expect(server.files["2026-11-03_deed.md"]).toBe("v2");
  });

  test("a second click while the first save is running makes no copy", async () => {
    const server = fakeServer();
    const post = server.http.postJSON;
    let release;
    const gate = new Promise((r) => {
      release = r;
    });
    server.http.postJSON = async (...args) => {
      await gate;
      return post(...args);
    };
    const { el } = page(server);
    await settle();
    button(el, "New note").click();
    el["notes-editor-name"].value = "deed";
    el["notes-editor-text"].value = "v1";
    el["notes-editor-save"].click();
    el["notes-editor-save"].click();
    release();
    await settle();
    await settle();
    expect(Object.keys(server.files)).toEqual(["2026-11-03_deed.md"]);
  });

  test("a saved note survives a reload and reopens with its text", async () => {
    const server = fakeServer({ "2026-11-03_deed.md": "kept text" });
    const { el } = page(server);
    await settle();
    button(el, "2026-11-03_deed.md").click();
    await settle();
    expect(el["notes-editor-text"].value).toBe("kept text");
    el["notes-editor-text"].value = "edited";
    el["notes-editor-save"].click();
    await settle();
    expect(server.files["2026-11-03_deed.md"]).toBe("edited");
    expect(el["notes-editor-status"].textContent).toBe("Saved.");
  });

  test("a missing name says so instead of doing nothing", async () => {
    const server = fakeServer();
    const { el } = page(server);
    await settle();
    button(el, "New note").click();
    el["notes-editor-text"].value = "text";
    el["notes-editor-save"].click();
    await settle();
    expect(server.calls.some(([m]) => m === "POST")).toBe(false);
    expect(el["notes-editor-status"].textContent).toContain("name");
  });

  test("server and network errors are shown, with their reason", async () => {
    const server = fakeServer();
    const { el } = page(server);
    await settle();
    button(el, "New note").click();
    el["notes-editor-name"].value = "x";
    el["notes-editor-text"].value = "   ";
    el["notes-editor-save"].click();
    await settle();
    expect(el["notes-editor-status"].textContent).toContain("Nothing to save.");

    el["notes-editor-text"].value = "real text";
    server.http.fail = "HTTP 500 — disk full";
    el["notes-editor-save"].click();
    await settle();
    expect(el["notes-editor-status"].textContent).toContain("disk full");
  });
});
