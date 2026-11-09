import { describe, expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { createNotes, markdownHtml } from "../boot/notes.js";
import { FakeDocument, FakeElement } from "./_fake-dom.js";

const IDS = [
  "notes-landing",
  "notes-editor",
  "notes-editor-title",
  "notes-editor-name",
  "notes-editor-text",
  "notes-editor-save",
  "notes-editor-refresh",
  "notes-editor-back",
  "notes-editor-status",
  "notes-editor-preview",
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
        return {
          ok: true,
          filename: name,
          note: files[name],
          revision: revision(files[name]),
        };
      }
      const names = Object.keys(files).sort().reverse();
      const revisions = Object.fromEntries(
        names.map((n) => [n, revision(files[n])]),
      );
      return { ok: true, notes: names, revisions };
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
        return { ok: true, filename: name, revision: revision(files[name]) };
      }
      if (url === "/api/note-write") {
        if (!(body.filename in files))
          throw new Error("HTTP 404 — Note not found");
        files[body.filename] = body.note;
        return {
          ok: true,
          filename: body.filename,
          revision: revision(files[body.filename]),
        };
      }
      throw new Error("HTTP 404");
    },
  };
  return { files, calls, http };
}

function revision(value) {
  return createHash("sha256").update(value).digest("hex");
}

/**
 * An isolated in-memory stand-in for localStorage. Each test gets its own by
 * default (via page()'s default parameter) so the unread-read-state feature
 * never leaks between tests through a real, process-wide globalThis.localStorage
 * — only a test that explicitly reuses the same instance (simulating EG
 * reloading the same browser) shares one.
 */
function createFakeStorage() {
  const store = new Map();
  return {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
  };
}

function page(server, { storage = createFakeStorage() } = {}) {
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
  const api = createNotes({ doc, http: server.http, storage });
  return { doc, el, api, storage };
}

const settle = () => new Promise((r) => setTimeout(r, 0));
// Note buttons may now sit inside a category <details>, not directly under
// notes-landing, so this walks the whole subtree rather than just one level.
const buttons = (el) => el["notes-landing"].querySelectorAll(".notes-choice");
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

  test("Refresh Notes reloads persisted text without reloading the page", async () => {
    const server = fakeServer({ "2026-11-03_deed.md": "persisted v1" });
    const { el } = page(server);
    await settle();
    button(el, "2026-11-03_deed.md").click();
    await settle();
    server.files["2026-11-03_deed.md"] = "persisted v2";
    el["notes-editor-refresh"].click();
    await settle();
    expect(el["notes-editor-text"].value).toBe("persisted v2");
    expect(
      server.calls.filter(
        ([method, url]) => method === "GET" && url.includes("filename="),
      ).length,
    ).toBe(2);
    // Both note reads (open, then refresh) carry a cache-busting _read; the list load has its own.
    expect(
      server.calls.filter(
        ([method, url]) =>
          method === "GET" &&
          url.includes("filename=") &&
          url.includes("_read="),
      ).length,
    ).toBe(2);
  });

  test("Refresh Notes preserves dirty edits unless confirmed", async () => {
    const server = fakeServer({ "2026-11-03_deed.md": "persisted" });
    const { el } = page(server);
    await settle();
    button(el, "2026-11-03_deed.md").click();
    await settle();
    el["notes-editor-text"].value = "unsaved edit";
    const confirm = globalThis.confirm;
    globalThis.confirm = () => false;
    try {
      el["notes-editor-refresh"].click();
      await settle();
      expect(el["notes-editor-text"].value).toBe("unsaved edit");
      expect(el["notes-editor-status"].textContent).toContain("cancelled");
    } finally {
      globalThis.confirm = confirm;
    }
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

  // A Bridge write lands through the same /api/notes read the browser already
  // polls every 5s (see pollSelected) — no separate "refresh" channel exists,
  // so these tests stand in for a ChatGPT Bridge task editing the file on disk.
  test("polling picks up a note a Bridge task wrote while this note was open", async () => {
    const server = fakeServer({ "2026-11-03_deed.md": "persisted v1" });
    const { el, api } = page(server);
    await settle();
    button(el, "2026-11-03_deed.md").click();
    await settle();

    server.files["2026-11-03_deed.md"] = "persisted v2 (bridge write)";
    await api.pollSelected();

    expect(el["notes-editor-text"].value).toBe("persisted v2 (bridge write)");
    expect(el["notes-editor-status"].textContent).toBe(
      "Updated from another Notes view.",
    );
  });

  test("polling does not clobber unsaved edits when a Bridge task writes the same note", async () => {
    const server = fakeServer({ "2026-11-03_deed.md": "persisted v1" });
    const { el, api } = page(server);
    await settle();
    button(el, "2026-11-03_deed.md").click();
    await settle();

    el["notes-editor-text"].value = "unsaved local edit";
    server.files["2026-11-03_deed.md"] =
      "bridge write, different from the edit above";
    await api.pollSelected();

    expect(el["notes-editor-text"].value).toBe("unsaved local edit");
    expect(el["notes-editor-status"].textContent).toContain(
      "changed elsewhere",
    );
  });

  test("polling is a no-op when no note is open, even if the Bridge wrote one", async () => {
    const server = fakeServer({ "2026-11-03_deed.md": "persisted v1" });
    const { api } = page(server);
    await settle();
    server.calls.length = 0;

    await api.pollSelected();

    expect(server.calls).toEqual([]);
  });

  test("a yellow highlight an agent wrote renders live in the preview, with no refresh", async () => {
    const server = fakeServer({ "2026-11-03_deed.md": "plain text" });
    const { el, api } = page(server);
    await settle();
    button(el, "2026-11-03_deed.md").click();
    await settle();
    expect(el["notes-editor-preview"].innerHTML).not.toContain(
      "notes-highlight-yellow",
    );

    server.files["2026-11-03_deed.md"] =
      "see the {{highlight:yellow}}legal description{{/highlight}} below";
    await api.pollSelected();

    expect(el["notes-editor-preview"].innerHTML).toContain(
      '<mark class="notes-highlight-yellow">legal description</mark>',
    );
  });

  test("the active deed warning stays readable when live polling rebuilds the preview", async () => {
    const warning =
      "[VERIFY WITH AN ATTORNEY OR THE PROBATE COURT: confirm authority before recording.]";
    const deed = [
      "# Personal Representative's Deed of Distribution",
      "## Authority of the Personal Representative",
      warning,
    ].join("\n");
    const server = fakeServer({ "2026-11-03_deed.md": deed });
    const { el, api } = page(server);
    await settle();
    button(el, "2026-11-03_deed.md").click();
    await settle();
    expect(el["notes-editor-preview"].innerHTML).toContain(warning);

    server.files["2026-11-03_deed.md"] = `${deed}\nUpdated by Bridge.`;
    await api.pollSelected();
    expect(el["notes-editor-preview"].innerHTML).toContain(warning);
    expect(el["notes-editor-preview"].innerHTML).toContain(
      "notes-deed-review-active-line",
    );

    server.files["2026-11-03_deed.md"] = deed;
    await api.refreshSelected();
    expect(el["notes-editor-preview"].innerHTML).toContain(warning);
    expect(el["notes-editor-preview"].innerHTML).toContain(
      "notes-deed-review-active-line",
    );
  });

  test("the deed preview marks preparer, legal-description, and tax review lines without changing Markdown", async () => {
    const deed = [
      "# Personal Representative's Deed of Distribution",
      "Prepared by: [NOT VERIFIED]",
      "Legal description: Lot <1> & parcel 42 [VERIFY]",
      "Transfer-tax exemption applies; property-tax exemption review required. [NOT VERIFIED]",
      "Sources for This Draft: county records",
    ].join("\n");
    const server = fakeServer({ "personal-representative-deed.md": deed });
    const { el } = page(server);
    await settle();
    button(el, "personal-representative-deed.md").click();
    await settle();

    const html = el["notes-editor-preview"].innerHTML;
    expect(html.match(/notes-deed-review-/g)?.length).toBe(3);
    expect(html).toContain("notes-deed-review-preparer");
    expect(html).toContain("notes-deed-review-legal-description");
    expect(html).toContain("notes-deed-review-tax-language");
    expect(html).toContain("Lot &lt;1&gt; &amp; parcel 42");
    expect(html).not.toContain("Sources for This Draft</mark>");
    expect(el["notes-editor-text"].value).toBe(deed);
    expect(server.files["personal-representative-deed.md"]).toBe(deed);
  });

  test("deed review marks do not leak to an unrelated note", async () => {
    const text =
      "Personal Representative: unrelated note\nLegal description\nProperty-tax exemption";
    const server = fakeServer({ "estate-notes.md": text });
    const { el } = page(server);
    await settle();
    button(el, "estate-notes.md").click();
    await settle();
    expect(el["notes-editor-preview"].innerHTML).not.toContain(
      "notes-deed-review-",
    );
  });

  test("a live poll update preserves the textarea caret and both panes' scroll position", async () => {
    const server = fakeServer({ "2026-11-03_deed.md": "line one\nline two" });
    const { el, api } = page(server);
    await settle();
    button(el, "2026-11-03_deed.md").click();
    await settle();
    el["notes-editor-text"].selectionStart = 4;
    el["notes-editor-text"].selectionEnd = 4;
    el["notes-editor-text"].scrollTop = 42;
    el["notes-editor-preview"].scrollTop = 17;

    server.files["2026-11-03_deed.md"] =
      "line one\nline two\nline three (bridge write)";
    await api.pollSelected();

    expect(el["notes-editor-text"].value).toBe(
      "line one\nline two\nline three (bridge write)",
    );
    expect(el["notes-editor-text"].selectionStart).toBe(4);
    expect(el["notes-editor-text"].selectionEnd).toBe(4);
    expect(el["notes-editor-text"].scrollTop).toBe(42);
    expect(el["notes-editor-preview"].scrollTop).toBe(17);
  });

  describe("markdownHtml — color/highlight spans (notes_formatting.py's markup)", () => {
    test("a highlight span becomes a <mark>, a color span becomes a colored <span>", () => {
      const html = markdownHtml(
        "{{highlight:yellow}}important{{/highlight}} and {{color:red}}urgent{{/color}}",
      );
      expect(html).toContain(
        '<mark class="notes-highlight-yellow">important</mark>',
      );
      expect(html).toContain('<span class="notes-color-red">urgent</span>');
    });

    test("an unknown color name renders as the literal markup text, not a span", () => {
      const html = markdownHtml("{{highlight:plaid}}text{{/highlight}}");
      expect(html).toContain("{{highlight:plaid}}text{{/highlight}}");
      expect(html).not.toContain("<mark");
    });

    test("bold/code still apply to the rest of the line outside a span", () => {
      const html = markdownHtml(
        "**bold** {{highlight:yellow}}hi{{/highlight}} `code`",
      );
      expect(html).toContain("<strong>bold</strong>");
      expect(html).toContain("<code>code</code>");
      expect(html).toContain('<mark class="notes-highlight-yellow">hi</mark>');
    });
  });

  describe("markdownHtml — Markdown source links", () => {
    test("a [label](https://...) link becomes a real, safely-targeted anchor", () => {
      const html = markdownHtml(
        "[County Register of Deeds](https://example.gov/search)",
      );
      expect(html).toContain(
        '<a href="https://example.gov/search" target="_blank" rel="noopener noreferrer">County Register of Deeds</a>',
      );
    });

    test("http:// links are linked too", () => {
      const html = markdownHtml("[old archive](http://example.org/archive)");
      expect(html).toContain(
        '<a href="http://example.org/archive" target="_blank" rel="noopener noreferrer">old archive</a>',
      );
    });

    test("javascript:, data:, file:, relative, and non-http(s) links are never linked", () => {
      const unsafe = [
        "[x](javascript:alert(1))",
        "[x](data:text/html,<script>alert(1)</script>)",
        "[x](file:///etc/passwd)",
        "[x](/dashboard/internal)",
        "[x](ftp://example.com/file)",
      ];
      for (const line of unsafe) {
        expect(markdownHtml(line)).not.toContain("<a ");
      }
    });

    test("label and URL special characters are escaped, not injected as HTML", () => {
      const html = markdownHtml(
        '[Click <here> & "verify"](https://example.com/a?b=1&c=2)',
      );
      expect(html).toContain(
        '<a href="https://example.com/a?b=1&amp;c=2" target="_blank" rel="noopener noreferrer">Click &lt;here&gt; &amp; &quot;verify&quot;</a>',
      );
      expect(html).not.toContain("<script>");
    });

    test("a link cannot break out of the href attribute with a quote", () => {
      const html = markdownHtml(
        '[x](https://example.com/"><script>alert(1)</script>)',
      );
      expect(html).not.toContain("<script>");
      expect(html).not.toContain('"><script');
    });

    test("a link written inside `code` stays plain text, not an anchor", () => {
      const html = markdownHtml("see `[label](https://example.com)` in code");
      expect(html).toContain("<code>[label](https://example.com)</code>");
      expect(html).not.toContain("<a ");
    });

    test("bold and highlight marks around a link are unaffected", () => {
      const html = markdownHtml(
        "**Source:** [county site](https://example.gov) {{highlight:yellow}}verify{{/highlight}}",
      );
      expect(html).toContain("<strong>Source:</strong>");
      expect(html).toContain(
        '<a href="https://example.gov" target="_blank" rel="noopener noreferrer">county site</a>',
      );
      expect(html).toContain(
        '<mark class="notes-highlight-yellow">verify</mark>',
      );
    });

    test("a heading can contain a link", () => {
      const html = markdownHtml(
        "## Sources: [county records](https://example.gov)",
      );
      expect(html).toContain(
        '<h2>Sources: <a href="https://example.gov" target="_blank" rel="noopener noreferrer">county records</a></h2>',
      );
    });
  });

  describe("category accordion", () => {
    const categories = (el) =>
      el["notes-landing"].children.filter((c) => c.tagName === "DETAILS");
    const summaryOf = (details) =>
      details.children.find((c) => c.tagName === "SUMMARY");

    test("a note named with a category slug sits under that category's own details, closed by default", async () => {
      const server = fakeServer({
        "2026-11-03_01-scoreboard-development-starter.md": "scoreboard notes",
        "2026-11-03_deed.md": "pre-existing, no category token",
      });
      const { el } = page(server);
      await settle();

      const groups = categories(el);
      const scoreboard = groups.find((d) =>
        summaryOf(d).textContent.startsWith("01. Scoreboard Development"),
      );
      expect(scoreboard).toBeTruthy();
      expect(summaryOf(scoreboard).textContent).toBe(
        "01. Scoreboard Development (1 note)",
      );
      expect(scoreboard.getAttribute("open")).toBeNull();
      expect(
        button(el, "2026-11-03_01-scoreboard-development-starter.md"),
      ).toBeTruthy();
    });

    test("a note without a category token lands in 'All other notes', open by default", async () => {
      const server = fakeServer({ "2026-11-03_deed.md": "kept text" });
      const { el } = page(server);
      await settle();

      const groups = categories(el);
      const other = groups.find((d) =>
        summaryOf(d).textContent.startsWith("All other notes"),
      );
      expect(other).toBeTruthy();
      expect(summaryOf(other).textContent).toBe("All other notes (1 note)");
      expect(other.getAttribute("open")).toBe("");
      // Unaffected by the new grouping: still clickable, still opens unchanged.
      button(el, "2026-11-03_deed.md").click();
      await settle();
      expect(el["notes-editor-text"].value).toBe("kept text");
    });

    test("all 10 standing categories render even with no notes in any of them yet", async () => {
      const server = fakeServer();
      const { el } = page(server);
      await settle();

      const groups = categories(el);
      const standing = groups.filter((d) =>
        /^\d{2}\. /.test(summaryOf(d).textContent),
      );
      expect(standing.length).toBe(10);
      for (const details of standing) {
        expect(summaryOf(details).textContent).toContain("(0 notes)");
        expect(details.getAttribute("open")).toBeNull();
      }
    });

    test("'New note' stays a direct, always-visible control outside any category", async () => {
      const server = fakeServer({
        "2026-11-03_01-scoreboard-development.md": "x",
      });
      const { el } = page(server);
      await settle();
      const direct = el["notes-landing"].children;
      expect(
        direct.some(
          (c) => c.tagName === "BUTTON" && c.textContent === "New note",
        ),
      ).toBe(true);
    });
  });
});
