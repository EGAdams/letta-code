// notes.js — the note selection page, backed by the existing filesystem repository.
export function createNotes({ doc, http }) {
  const landing = doc.getElementById("notes-landing");
  const editor = doc.getElementById("notes-editor");
  const title = doc.getElementById("notes-editor-title");
  const textarea = doc.getElementById("notes-editor-text");
  const status = doc.getElementById("notes-editor-status");
  let selected = "";

  const setStatus = (message) => {
    if (status) status.textContent = message;
  };
  const open = async (filename) => {
    const result = await http.getJSON(
      `/api/notes?filename=${encodeURIComponent(filename)}`,
    );
    selected = filename;
    title.textContent = filename;
    textarea.value = result.note || "";
    landing.classList.add("hidden");
    editor.classList.remove("hidden");
    setStatus("");
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
        button.addEventListener("click", () =>
          open(filename).catch(() => setStatus("Could not open note.")),
        );
        landing.appendChild(button);
      });
      const create = doc.createElement("button");
      create.type = "button";
      create.className = "am-btn notes-choice";
      create.textContent = "New note";
      create.addEventListener("click", () => {
        selected = "";
        title.textContent = "New note";
        textarea.value = "";
        landing.classList.add("hidden");
        editor.classList.remove("hidden");
      });
      landing.appendChild(create);
    } catch {
      landing.textContent = "Could not load notes.";
    }
  };
  doc
    .getElementById("notes-editor-save")
    ?.addEventListener("click", async () => {
      if (!selected) {
        const filename = globalThis.prompt?.("Name this note")?.trim();
        if (!filename) return;
        const result = await http.postJSON("/api/note-save", {
          filename,
          note: textarea.value,
        });
        setStatus(
          result.ok ? `Saved ${result.filename}.` : "Could not save note.",
        );
        if (result.ok) load();
        return;
      }
      const result = await http.postJSON("/api/note-write", {
        filename: selected,
        note: textarea.value,
      });
      setStatus(result.ok ? "Saved." : "Could not save note.");
    });
  doc.getElementById("notes-editor-back")?.addEventListener("click", () => {
    editor.classList.add("hidden");
    landing.classList.remove("hidden");
    load();
  });
  load();
  return { load };
}
