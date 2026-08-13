import { describe, expect, test } from "bun:test";
import { ListenerState } from "../abstract/continuous-listener.interface.js";
import { NoteCommandPanelRenderer } from "../implementation/note-command-panel.js";
import { ReadOnlyNoteSurface } from "../implementation/textarea-note-surfaces.js";
import { FakeDocument } from "./_fake-dom.js";

class FakeListener {
  constructor() {
    this.state = ListenerState.IDLE;
    this.starts = 0;
    this.stops = 0;
    this._callbacks = {};
  }
  get isListening() {
    return this.state === ListenerState.LISTENING;
  }
  setCallbacks(callbacks) {
    Object.assign(this._callbacks, callbacks);
  }
  async start() {
    this.starts += 1;
    this.state = ListenerState.LISTENING;
    this._callbacks.onStateChange?.(this.state);
    return true;
  }
  stop() {
    this.stops += 1;
    this.state = ListenerState.IDLE;
    this._callbacks.onStateChange?.(this.state);
  }
  emit(text, isFinal) {
    return this._callbacks.onResult?.(text, isFinal);
  }
  fail(message) {
    this._callbacks.onError?.(message);
  }
}

function setup({ verdicts = {}, outcomeFor } = {}) {
  const doc = new FakeDocument();
  const container = doc.createElement("div");
  container.id = "note-command-box";
  doc.add(container);

  const note = new ReadOnlyNoteSurface({ doc });
  note.setText("Today Roy and I worked on the scoreboard");

  const listener = new FakeListener();
  const asked = [];
  const applied = [];
  const api = new NoteCommandPanelRenderer({
    note,
    listener,
    completenessDetector: {
      assess: async (text) => {
        asked.push(text);
        return { complete: !!verdicts[text], reason: "" };
      },
    },
    commandInterpreter: {
      apply: async (noteText, command) => {
        applied.push({ note: noteText, command });
        return (
          outcomeFor?.(noteText, command) || {
            kind: "edit",
            note: `${noteText}.`,
            saved: null,
            message: "",
          }
        );
      },
    },
    doc,
  }).render("note-command-box");

  return { doc, container, note, listener, asked, applied, api };
}

const q = (container, selector) => container.querySelector(selector);

describe("NoteCommandPanelRenderer", () => {
  test("renders its own command textarea, separate from the note", () => {
    const ctx = setup();
    const commandEl = q(ctx.container, ".note-command-input");
    expect(commandEl.tagName).toBe("TEXTAREA");
    expect(commandEl).not.toBe(ctx.note.element);
    expect(commandEl.readOnly).toBeFalsy();
  });

  test("shows the accumulated command and only edits the note once complete", async () => {
    const ctx = setup({ verdicts: { "Put a period at the end": true } });
    const commandEl = q(ctx.container, ".note-command-input");

    await ctx.listener.emit("Put a", true);
    expect(commandEl.value).toBe("Put a");
    expect(ctx.applied).toEqual([]);
    expect(ctx.note.getText()).toBe("Today Roy and I worked on the scoreboard");

    await ctx.listener.emit("period at the end", true);
    expect(ctx.applied).toEqual([
      {
        note: "Today Roy and I worked on the scoreboard",
        command: "Put a period at the end",
      },
    ]);
    expect(ctx.note.getText()).toBe(
      "Today Roy and I worked on the scoreboard.",
    );
    expect(commandEl.value).toBe("");
  });

  test("the Run button executes a typed command without the detector", async () => {
    const ctx = setup();
    const commandEl = q(ctx.container, ".note-command-input");
    commandEl.value = "put a period at the end";
    await q(ctx.container, ".note-command-run").click();
    expect(ctx.asked).toEqual([]);
    expect(ctx.applied.at(-1).command).toBe("put a period at the end");
  });

  test("the listen button toggles the listener and its own label", async () => {
    const ctx = setup();
    const listenBtn = q(ctx.container, ".note-command-listen");
    expect(listenBtn.textContent).toBe("Start Command Listening");
    await listenBtn.click();
    expect(ctx.listener.starts).toBe(1);
    expect(listenBtn.textContent).toBe("Stop Command Listening");
    await listenBtn.click();
    expect(ctx.listener.stops).toBe(1);
    expect(listenBtn.textContent).toBe("Start Command Listening");
  });

  test("Clear empties the command box without touching the note", async () => {
    const ctx = setup();
    await ctx.listener.emit("Put a", true);
    await q(ctx.container, ".note-command-clear").click();
    expect(q(ctx.container, ".note-command-input").value).toBe("");
    expect(ctx.note.getText()).toBe("Today Roy and I worked on the scoreboard");
  });

  test("a listener error is reported instead of failing silently", () => {
    const ctx = setup();
    ctx.listener.fail("Microphone permission was denied.");
    expect(q(ctx.container, ".note-command-status").textContent).toBe(
      "Microphone permission was denied.",
    );
  });

  test("refuses to build without a note or a listener", () => {
    expect(() => new NoteCommandPanelRenderer({})).toThrow("NoteDocument");
    expect(() => new NoteCommandPanelRenderer({ note: {} })).toThrow(
      "ContinuousListener",
    );
  });
});
