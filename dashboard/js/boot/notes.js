// notes.js — the note selection page, backed by the existing filesystem repository.
//
// A new note is named in the editor's own name box, not a browser prompt():
// prompt() is blocked or auto-dismissed in embedded and automated browsers
// (ChatGPT's agent among them), and there it returned nothing, so Save did
// nothing and said nothing. Once a new note is saved, the editor holds its
// filename, so the next Save updates that file instead of creating a copy.
export function createNotes({ doc, http }) {
  const landing = doc.getElementById("notes-landing");
  const editor = doc.getElementById("notes-editor");
  const title = doc.getElementById("notes-editor-title");
  const nameBox = doc.getElementById("notes-editor-name");
  const textarea = doc.getElementById("notes-editor-text");
  const status = doc.getElementById("notes-editor-status");
  let selected = "";

  const setStatus = (message) => {
    if (status) status.textContent = message;
  };
  const reason = (error) => error?.message || "the dashboard did not answer";
  const showEditor = (filename, text) => {
    selected = filename;
    title.textContent = filename || "New note";
    textarea.value = text;
    if (nameBox) {
      nameBox.value = "";
      nameBox.classList[filename ? "add" : "remove"]("hidden");
    }
    landing.classList.add("hidden");
    editor.classList.remove("hidden");
    setStatus("");
  };
  const open = async (filename) => {
    const result = await http.getJSON(
      `/api/notes?filename=${encodeURIComponent(filename)}`,
    );
    showEditor(filename, result.note || "");
  };
  const load = async () => {
    landing.textContent = "Loading notes…";
    try {
      const result = await http.getJSON("/api/notes");
      landing.textContent = "";
      (result.notes || []).forEach((filename) => {
        const button = doc.createElement("button");
        button.type = "button";
        button.className = "am-btn notes-choice";
        button.textContent = filename;
        button.addEventListener("click", () => {
          open(filename).catch((error) =>
            setStatus(`Could not open note: ${reason(error)}`),
          );
        });
        landing.appendChild(button);
      });
      const create = doc.createElement("button");
      create.type = "button";
      create.className = "am-btn notes-choice";
      create.textContent = "New note";
      create.addEventListener("click", () => {
        showEditor("", "");
      });
      landing.appendChild(create);
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
    title.textContent = result.filename;
    nameBox?.classList.add("hidden");
    setStatus(`Saved ${result.filename}.`);
  };
  const saveExisting = async () => {
    const result = await http.postJSON("/api/note-write", {
      filename: selected,
      note: textarea.value,
    });
    setStatus(
      result.ok
        ? "Saved."
        : `Could not save note: ${result.error || "unknown error"}`,
    );
  };
  doc
    .getElementById("notes-editor-save")
    ?.addEventListener("click", async () => {
      setStatus("Saving…");
      try {
        await (selected ? saveExisting() : saveNew());
      } catch (error) {
        setStatus(`Could not save note: ${reason(error)}`);
      }
    });
  doc.getElementById("notes-editor-back")?.addEventListener("click", () => {
    editor.classList.add("hidden");
    landing.classList.remove("hidden");
    load();
  });
  load();
  return { load };
}
