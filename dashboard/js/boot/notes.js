// notes.js — the note selection page, backed by the existing filesystem repository.
//
// A new note is named in the editor's own name box, not a browser prompt():
// prompt() is blocked or auto-dismissed in embedded and automated browsers
// (ChatGPT's agent among them), and there it returned nothing, so Save did
// nothing and said nothing. Once a new note is saved, the editor holds its
// filename, so the next Save updates that file instead of creating a copy.
import { MermaidView } from "../plans/mermaid-view.js";

const STARTER = `# Probate notes\n\n- Father: Louis Adams Sr.\n- PR: Louis Herbert Adams Jr.\n- Court-certified Letters of Authority in force: November 3, 2026\n- Deed distribution: not yet prepared\n\n## Verify\n\n- Verify the legal description.\n- Verify whether the estate actually closed.\n\n## Collaboration\n\nUse this note for decisions, questions, and handoffs with Lucia (Lucia is a female Spanish name and the notes/debug SME).\n`;

// The 10 standing categories for the Notes list, in display order. A note
// lands in one of these only if its filename carries the matching "NN-"
// token (see categoryFor) — never guessed from its content.
const CATEGORIES = [
  { prefix: "01", title: "Scoreboard Development" },
  { prefix: "02", title: "Finance & Bookkeeping" },
  { prefix: "03", title: "Tax Preparation" },
  { prefix: "04", title: "Probate & Real Estate" },
  { prefix: "05", title: "AI Agents" },
  { prefix: "06", title: "Star Trek Bridge & ADW" },
  { prefix: "07", title: "Dashboards & Web Interfaces" },
  { prefix: "08", title: "Document Automation" },
  { prefix: "09", title: "Computer Systems & Networking" },
  { prefix: "10", title: "Other Engineering Projects" },
];

/**
 * A saved note's filename is always `<save-date>_<slug>.md`
 * (FilesystemNoteRepository.save/slugify). Typing a name like
 * "01. Scoreboard Development" into the name box slugifies to a leading
 * "01-" token, which is the only signal used here. Any note saved before
 * this convention existed, or named without it, is not reclassified by
 * guessing at its content — it simply has no category.
 */
function categoryFor(filename) {
  const slug = String(filename || "")
    .replace(/\.md$/i, "")
    .replace(/^\d{4}-\d{2}-\d{2}_/, "");
  const match = slug.match(/^(\d{2})-/);
  return (match && CATEGORIES.find((c) => c.prefix === match[1])) || null;
}

/** Split a flat filename list into the 10 standing categories plus an "other" bucket. */
function groupNotes(filenames) {
  const groups = CATEGORIES.map((category) => ({ ...category, notes: [] }));
  const other = [];
  for (const filename of filenames) {
    const category = categoryFor(filename);
    const group = category && groups.find((g) => g.prefix === category.prefix);
    (group ? group.notes : other).push(filename);
  }
  return { groups, other };
}

// Unread tracking is per browser, not per account — this dashboard has no
// login, and a filesystem note has no owner field to key a server-side "seen
// by EG" record on. localStorage already backs another section's state
// (receptionist.js's `storage` parameter), so this follows the same
// dependency-injected pattern rather than reaching for globalThis directly,
// and makes no claim of syncing "read" across EG's other machines.
const READ_STATE_KEY = "notes-dashboard-read-state-v1";

function loadReadState(storage) {
  try {
    const raw = storage?.getItem(READ_STATE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveReadState(storage, state) {
  try {
    storage?.setItem(READ_STATE_KEY, JSON.stringify(state));
  } catch {
    /* a full or disabled store just means unread highlighting resets next load */
  }
}

/** Remove every child without relying on a browser-only innerHTML reset. */
function emptyElement(el) {
  for (const child of [...el.children]) child.remove();
}

const escapeHtml = (value) =>
  value.replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char],
  );

// Mirrors notes_formatting.COLORS' key set (dashboard/notes_formatting.py) —
// not its hex values, since here the name only picks a CSS class
// (.notes-highlight-<name> / .notes-color-<name> in dashboard.css). An
// unrecognized name is deliberately not in this set, matching that module's
// "unknown color name renders as the literal markup text" rule.
const SPAN_COLOR_NAMES = new Set([
  "red",
  "orange",
  "yellow",
  "green",
  "blue",
  "purple",
  "gray",
  "black",
]);
const SPAN_RE = /\{\{(color|highlight):([a-z]+)\}\}([\s\S]*?)\{\{\/\1\}\}/g;

/** **bold** and `code` only, same as before — applied to text outside any color/highlight span. */
function renderMarkdownInline(text) {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

/**
 * One line's `{{color:name}}`/`{{highlight:name}}` spans (notes_formatting.py's
 * markup, shared with the Word export and email draft) -> HTML, so a yellow
 * highlight an agent wrote to the note shows up the same way here. A span's
 * inner text does not get **bold** or `code` applied — same "kept simple on
 * purpose" rule as the Python parser — only the text outside spans does.
 */
function renderInlineSpans(text) {
  let html = "",
    pos = 0,
    match;
  // biome-ignore lint/suspicious/noAssignInExpressions: the standard regex-exec loop
  while ((match = SPAN_RE.exec(text))) {
    if (match.index > pos)
      html += renderMarkdownInline(text.slice(pos, match.index));
    const [full, kind, name, inner] = match;
    html += SPAN_COLOR_NAMES.has(name)
      ? `<${kind === "highlight" ? "mark" : "span"} class="notes-${kind}-${name}">${escapeHtml(inner)}</${kind === "highlight" ? "mark" : "span"}>`
      : escapeHtml(full);
    pos = SPAN_RE.lastIndex;
  }
  if (pos < text.length) html += renderMarkdownInline(text.slice(pos));
  return html;
}

// Review marks are deliberately a view concern.  They are only enabled for a
// note whose filename and title identify the Personal Representative's deed;
// ordinary notes must never acquire marks merely because they mention taxes or
// a legal description.  The source text is passed through the normal escaped
// Markdown renderer and then wrapped, so the deed remains byte-for-byte intact.
function isPersonalRepresentativeDeed(filename, source) {
  const deedFilename = String(filename || "")
    .toLowerCase()
    .includes("deed");
  const deedTitle =
    /personal representative(?:'s)?\s+deed|deed of distribution/i.test(source);
  return deedFilename && deedTitle;
}

// A review mark means "this still needs a person". A line is marked only while it holds something unresolved --
// a [BRACKETED] placeholder, "NOT VERIFIED" or "VERIFY" -- so a finished line (a Prepared by line with the
// preparer filled in) drops its mark and an open one keeps it. Purely a view rule: the note text is untouched.
const UNRESOLVED_RE = /\[[^\]\n]*\]|not\s+verified|\bverify\b/i;

function deedReviewKind(line) {
  if (!UNRESOLVED_RE.test(line)) return "";
  const text = line.toLowerCase();
  if (/prepared\s+by|preparer|personal representative|\bpr\b/.test(text))
    return "preparer";
  if (
    /legal description|property description|parcel description|parcel\s+(?:no|number)|tax parcel/.test(
      text,
    )
  )
    return "legal-description";
  if (
    /transfer[- ]tax|property[- ]tax|tax exemption|tax-exempt|uncapping/.test(
      text,
    )
  )
    return "tax-language";
  // Any other open placeholder (grantee, dates, notary, exceptions...) still needs a person -- except the
  // draft banner, which merely explains what brackets mean.
  if (/items in \[brackets\]/i.test(line)) return "";
  // Signing-day blanks such as "Dated: [____]" are filled by hand at signing, not review items.
  if (
    !/not\s+verified|\bverify\b|\[[^\]\n]*[A-Za-z][^\]\n]*\]/i.test(
      line.replace(/\[_*[A-Z]*_*\]/g, ""),
    )
  )
    return "";
  return "open-item";
}

function renderReviewedLine(line, reviewEnabled) {
  const rendered = renderInlineSpans(line);
  const kind = reviewEnabled ? deedReviewKind(line) : "";
  return kind
    ? `<mark class="notes-highlight-yellow notes-deed-review-${kind}">${rendered}</mark>`
    : rendered;
}

export function markdownHtml(source, { filename = "" } = {}) {
  const reviewEnabled = isPersonalRepresentativeDeed(filename, source);
  const lines = source.split(/\r?\n/);
  let html = "",
    list = false,
    mermaid = [];
  const closeList = () => {
    if (list) {
      html += "</ul>";
      list = false;
    }
  };
  for (const line of lines) {
    if (line.trim() === "```mermaid") {
      closeList();
      mermaid.push([]);
      continue;
    }
    if (mermaid.length && line.trim() === "```") {
      html += `<pre class="notes-mermaid-source">${escapeHtml(mermaid.pop().join("\n"))}</pre>`;
      continue;
    }
    if (mermaid.length) {
      mermaid[mermaid.length - 1].push(line);
      continue;
    }
    if (!line.trim()) {
      closeList();
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      closeList();
      html += `<h${heading[1].length}>${renderReviewedLine(heading[2], reviewEnabled)}</h${heading[1].length}>`;
      continue;
    }
    const item = line.match(/^[-*]\s+(.*)$/);
    if (item) {
      if (!list) {
        html += "<ul>";
        list = true;
      }
      html += `<li>${renderReviewedLine(item[1], reviewEnabled)}</li>`;
      continue;
    }
    closeList();
    html += `<p>${renderReviewedLine(line, reviewEnabled)}</p>`;
  }
  closeList();
  return html;
}

export function createNotes({ doc, http, storage = globalThis.localStorage }) {
  const landing = doc.getElementById("notes-landing");
  const diagnostic = doc.getElementById("notes-diagnostic");
  const editor = doc.getElementById("notes-editor");
  const title = doc.getElementById("notes-editor-title");
  const nameBox = doc.getElementById("notes-editor-name");
  const textarea = doc.getElementById("notes-editor-text");
  const status = doc.getElementById("notes-editor-status");
  const preview = doc.getElementById("notes-editor-preview");
  const monitor = doc.getElementById("notes-editor-monitor");
  const refreshButton = doc.getElementById("notes-editor-refresh");
  let mermaidView;
  let selected = "";
  let revision = "";
  let lastSavedText = "";
  let autosaveTimer;
  let pollTimer;
  let saving = false;
  // null means "this browser has never seen the feature" — the first load()
  // seeds it from whatever already exists so rollout never flashes old notes
  // as unread; every load/poll after that only flags a filename whose
  // revision disagrees with what's recorded here.
  let readState = loadReadState(storage);
  let seeded = readState !== null;
  if (!seeded) readState = {};

  const setStatus = (message) => {
    if (status) status.textContent = message;
  };
  const focusEditor = () => {
    editor.scrollIntoView?.({ behavior: "smooth", block: "start" });
    textarea.focus?.();
  };
  // Fails closed, matching the rest of the Notes path: a filename with no
  // revision in the response (older server, or it lost a race with a
  // concurrent delete) is never flagged unread rather than guessed at.
  const isUnread = (filename, revisions) => {
    const rev = revisions[filename];
    return !!rev && readState[filename] !== rev;
  };
  const markRead = (filename, rev) => {
    if (!filename || !rev || readState[filename] === rev) return;
    readState[filename] = rev;
    saveReadState(storage, readState);
  };
  const reason = (error) => error?.message || "the dashboard did not answer";
  // Notes are mutable Markdown outside the dashboard checkout. A proxy or
  // browser can otherwise replay an older GET even though the API response
  // is marked no-store; each read must identify the current read operation.
  const noteURL = (filename) => {
    const query = new URLSearchParams({ filename, _read: String(Date.now()) });
    return `/api/notes?${query}`;
  };
  const updatePreview = async () => {
    if (!preview) return;
    mermaidView?.destroyAll();
    preview.innerHTML = markdownHtml(textarea.value, { filename: selected });
    const blocks = [...preview.querySelectorAll(".notes-mermaid-source")];
    if (globalThis.mermaid && blocks.length) {
      mermaidView = new MermaidView({
        mermaid: globalThis.mermaid,
        svgPanZoom: globalThis.svgPanZoom,
        doc,
        win: globalThis,
        config: { securityLevel: "strict" },
      });
      for (const block of blocks) {
        const code = block.textContent;
        const mount = doc.createElement("div");
        block.replaceWith(mount);
        await mermaidView.render(mount, { code });
      }
    }
    if (monitor)
      monitor.textContent = `Monitor: preview updated ${new Date().toLocaleTimeString()}. Local page state only; no live screen sync.`;
  };
  const showEditor = (filename, text, nextRevision = "") => {
    selected = filename;
    title.textContent = filename || "New note";
    textarea.value = text ?? (filename ? "" : STARTER);
    revision = nextRevision;
    lastSavedText = textarea.value;
    if (nameBox) {
      nameBox.value = "";
      nameBox.classList[filename ? "add" : "remove"]("hidden");
    }
    landing.classList.add("hidden");
    editor.classList.remove("hidden");
    setStatus("");
    updatePreview();
    focusEditor();
  };
  const open = async (filename) => {
    const result = await http.getJSON(noteURL(filename));
    showEditor(filename, result.note || "", result.revision || "");
    markRead(filename, result.revision);
  };
  const refreshSelected = async () => {
    if (!selected) {
      setStatus("Open a saved note before refreshing.");
      return;
    }
    const dirty = textarea.value !== lastSavedText;
    if (dirty) {
      const confirmRefresh = globalThis.confirm;
      if (
        typeof confirmRefresh !== "function" ||
        !confirmRefresh(
          "Discard your unsaved edits and refresh this note from persisted state?",
        )
      ) {
        setStatus("Refresh cancelled; your edits are preserved.");
        return;
      }
    }
    const hadFocus = doc.activeElement === textarea;
    refreshButton?.setAttribute("aria-busy", "true");
    setStatus("Refreshing…");
    try {
      const result = await http.getJSON(noteURL(selected));
      textarea.value = result.note || "";
      revision = result.revision || "";
      lastSavedText = textarea.value;
      markRead(selected, revision);
      await updatePreview();
      setStatus("Refreshed from persisted state.");
      if (hadFocus) textarea.focus();
    } catch (error) {
      setStatus(`Could not refresh note: ${reason(error)}`);
    } finally {
      refreshButton?.removeAttribute("aria-busy");
    }
  };
  // Applying a Bridge-written revision replaces textarea.value and rebuilds
  // the preview's innerHTML wholesale (there is no smaller DOM to diff
  // against — the note is one Markdown blob) but neither of those is the
  // whole page, and both reset their own scroll/caret as a side effect of
  // that assignment — restored below so EG's reading position and any
  // textarea caret survive a highlight an agent just committed showing up.
  const restoreAfterPatch = () => {
    const caretStart = textarea.selectionStart;
    const caretEnd = textarea.selectionEnd;
    const textareaScroll = textarea.scrollTop;
    const previewScroll = preview?.scrollTop;
    return (newText) => {
      if (typeof caretStart === "number") {
        const max = newText.length;
        textarea.selectionStart = Math.min(caretStart, max);
        textarea.selectionEnd = Math.min(caretEnd ?? caretStart, max);
      }
      textarea.scrollTop = textareaScroll;
      if (preview && typeof previewScroll === "number")
        preview.scrollTop = previewScroll;
    };
  };
  const pollSelected = async () => {
    if (!selected || globalThis.document?.visibilityState === "hidden") return;
    try {
      const result = await http.getJSON(noteURL(selected));
      if (result.revision === revision) return;
      if (textarea.value !== lastSavedText || saving) {
        setStatus(
          "Note changed elsewhere; your edits are preserved. Save when ready.",
        );
        return;
      }
      const restore = restoreAfterPatch();
      textarea.value = result.note || "";
      revision = result.revision || "";
      lastSavedText = textarea.value;
      markRead(selected, revision);
      await updatePreview();
      restore(textarea.value);
      setStatus("Updated from another Notes view.");
    } catch (_) {
      /* a later poll can recover from a transient request failure */
    }
  };
  // 3s auto-refresh for the note list itself, mirroring pollSelected's cadence
  // for the one open note — so a note an agent just created or edited lights
  // up without EG having to click Refresh Notes or reopen the Notes tab.
  const pollLanding = async () => {
    if (landing.classList.contains("hidden")) return;
    if (globalThis.document?.visibilityState === "hidden") return;
    try {
      const result = await http.getJSON(`/api/notes?_read=${Date.now()}`);
      renderLanding(result.notes || [], result.revisions || {});
    } catch (_) {
      /* a later poll can recover from a transient request failure */
    }
  };
  const noteButton = (filename, unread) => {
    const button = doc.createElement("button");
    button.type = "button";
    button.className = "am-btn notes-choice";
    if (unread) {
      button.classList.add("notes-unread");
      button.setAttribute("aria-label", `${filename} — unread, new or updated`);
    }
    button.textContent = filename;
    button.addEventListener("click", () => {
      open(filename).catch((error) =>
        setStatus(`Could not open note: ${reason(error)}`),
      );
    });
    return button;
  };
  // Badge lives as a sibling of the button, not inside it: nesting it inside
  // would change what a real browser reports as the button's .textContent
  // (a live concatenation of all descendant text), and nothing else in this
  // file identifies a note's button by anything other than that exact
  // filename string.
  const noteRow = (filename, unread) => {
    const row = doc.createElement("div");
    row.className = unread ? "notes-row notes-row-unread" : "notes-row";
    const badge = doc.createElement("span");
    badge.className = "notes-unread-badge";
    badge.textContent = "NEW";
    if (!unread) badge.classList.add("hidden");
    row.appendChild(badge);
    row.appendChild(noteButton(filename, unread));
    return row;
  };
  // One independently-expanding/collapsing <details> per category — the
  // same native disclosure widget already used elsewhere in this dashboard
  // (e.g. mazda-tool-reconciliation.js's "what was checked" panel), so
  // toggling, keyboard support (Enter/Space on the summary) and the
  // expanded/collapsed state exposed to assistive tech all come from the
  // browser itself rather than a second, hand-rolled accordion.
  const categoryAccordion = (
    categoryKey,
    label,
    count,
    unreadCount,
    filenames,
    unreadSet,
    { openByDefault = false } = {},
  ) => {
    const details = doc.createElement("details");
    details.className = "notes-category";
    // A stable key independent of the summary's own text — that text now
    // carries an unread count that changes every poll, so it can't double as
    // the identity used to restore this category's open/closed state.
    details.dataset.categoryKey = categoryKey;
    if (openByDefault) details.setAttribute("open", "");
    const summary = doc.createElement("summary");
    const notesLabel = `${count} note${count === 1 ? "" : "s"}`;
    summary.textContent =
      unreadCount > 0
        ? `${label} (${notesLabel}, ${unreadCount} unread)`
        : `${label} (${notesLabel})`;
    details.appendChild(summary);
    const body = doc.createElement("div");
    body.className = "notes-category-body";
    if (filenames.length) {
      filenames.forEach((filename) => {
        body.appendChild(noteRow(filename, unreadSet.has(filename)));
      });
    } else {
      const empty = doc.createElement("p");
      empty.className = "am-dim";
      empty.textContent = "No notes in this category yet.";
      body.appendChild(empty);
    }
    details.appendChild(body);
    return details;
  };
  // Rebuilds the category list in place. Called by both the initial load()
  // and the 5s pollLanding() — reused rather than duplicated so a note an
  // agent just created or edited is picked up the same way either path
  // found it. Each category's open/closed state survives the rebuild
  // (keyed by categoryKey, not by its summary text, which now carries an
  // unread count) so a poll never snaps an accordion EG opened back shut.
  let landingRendered = false;
  const renderLanding = (filenames, revisions) => {
    const previouslyOpen = new Set(
      [...landing.children]
        .filter(
          (c) => c.tagName === "DETAILS" && c.getAttribute("open") !== null,
        )
        .map((c) => c.dataset.categoryKey),
    );
    const unreadSet = new Set(filenames.filter((f) => isUnread(f, revisions)));
    emptyElement(landing);
    const { groups, other } = groupNotes(filenames);
    // All 10 standing categories render every time, even before any note
    // carries that category's token — the operator needs a header to open
    // (and a name to type into the editor's name box) before a category can
    // have a first note at all.
    groups.forEach((group) => {
      const unreadCount = group.notes.filter((f) => unreadSet.has(f)).length;
      landing.appendChild(
        categoryAccordion(
          group.prefix,
          `${group.prefix}. ${group.title}`,
          group.notes.length,
          unreadCount,
          group.notes,
          unreadSet,
          { openByDefault: previouslyOpen.has(group.prefix) },
        ),
      );
    });
    if (other.length) {
      // Open by default on the very first render: every note saved before
      // this convention existed (including the Deed note) lives here, and
      // must stay as easy to find as the old flat list — not hidden behind
      // an extra click. A later rebuild (pollLanding) instead respects
      // whatever EG last left it at.
      const unreadCount = other.filter((f) => unreadSet.has(f)).length;
      landing.appendChild(
        categoryAccordion(
          "other",
          "All other notes",
          other.length,
          unreadCount,
          other,
          unreadSet,
          {
            openByDefault: landingRendered ? previouslyOpen.has("other") : true,
          },
        ),
      );
    }
    const create = doc.createElement("button");
    create.type = "button";
    create.className = "am-btn notes-choice";
    create.textContent = "New note";
    create.addEventListener("click", () => {
      showEditor("", "");
    });
    landing.appendChild(create);
    landingRendered = true;
  };
  const load = async () => {
    landing.textContent = "Loading notes…";
    try {
      const result = await http.getJSON(`/api/notes?_read=${Date.now()}`);
      const filenames = result.notes || [];
      const revisions = result.revisions || {};
      if (diagnostic) {
        diagnostic.textContent = `Notes directory is active on the dashboard host. ${filenames.length} persisted note(s) found; open the exact deed filename before editing.`;
      }
      // First time this feature has ever run in this browser: treat every
      // note that already exists as already seen, so rollout never flashes
      // old, unrelated notes as unread. Only a note that shows up or changes
      // after this point is new to readState.
      if (!seeded) {
        for (const filename of filenames)
          if (revisions[filename]) readState[filename] = revisions[filename];
        saveReadState(storage, readState);
        seeded = true;
      }
      renderLanding(filenames, revisions);
    } catch (error) {
      landing.textContent = `Could not load notes: ${reason(error)}`;
    }
  };
  const saveNew = async () => {
    const name = (nameBox?.value ?? globalThis.prompt?.("Name this note") ?? "")
      .toString()
      .trim();
    if (!name) {
      setStatus("Type a name for this note first.");
      return;
    }
    const result = await http.postJSON("/api/note-save", {
      filename: name,
      note: textarea.value,
    });
    if (!result.ok) {
      setStatus(`Could not save note: ${result.error || "unknown error"}`);
      return;
    }
    selected = result.filename;
    revision = result.revision || "";
    lastSavedText = textarea.value;
    markRead(selected, revision);
    title.textContent = result.filename;
    nameBox?.classList.add("hidden");
    setStatus(`Saved ${result.filename}.`);
  };
  const saveExisting = async () => {
    const result = await http.postJSON("/api/note-write", {
      filename: selected,
      note: textarea.value,
      expected_revision: revision,
    });
    if (result.ok) {
      revision = result.revision || revision;
      lastSavedText = textarea.value;
      markRead(selected, revision);
    }
    setStatus(
      result.ok
        ? "Saved."
        : `Could not save note: ${result.error || "unknown error"}`,
    );
  };
  const save = async () => {
    if (saving) return false;
    // One save at a time: a second click before a new note's first save
    // returns would otherwise create a second copy of it.
    saving = true;
    setStatus("Saving…");
    try {
      await (selected ? saveExisting() : saveNew());
      return true;
    } catch (error) {
      setStatus(`Could not save note: ${reason(error)}`);
      return false;
    } finally {
      saving = false;
    }
  };
  doc.getElementById("notes-editor-save")?.addEventListener("click", save);
  refreshButton?.addEventListener("click", () => {
    refreshSelected();
  });
  textarea?.addEventListener("input", () => {
    updatePreview();
    clearTimeout(autosaveTimer);
    if (selected) {
      autosaveTimer = setTimeout(() => {
        if (!saving && textarea.value !== lastSavedText) {
          doc.getElementById("notes-editor-save")?.click();
        }
      }, 1200);
    }
  });
  doc.getElementById("notes-editor-back")?.addEventListener("click", () => {
    editor.classList.add("hidden");
    landing.classList.remove("hidden");
    load();
  });
  load();
  pollTimer = setInterval(() => {
    pollSelected();
    pollLanding();
  }, 3000);
  return {
    load,
    pollSelected,
    pollLanding,
    refreshSelected,
    openNew: () => showEditor("", ""),
    setName: (value) => {
      if (nameBox) nameBox.value = String(value ?? "").trim();
    },
    save,
    read: () => {
      if (typeof globalThis.speechSynthesis?.speak !== "function") return;
      globalThis.speechSynthesis.cancel?.();
      globalThis.speechSynthesis.speak(
        new globalThis.SpeechSynthesisUtterance(
          textarea.value || "The note is empty.",
        ),
      );
    },
    textarea,
    status,
    stop: () => clearInterval(pollTimer),
  };
}
