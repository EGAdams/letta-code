import { describe, expect, test } from "bun:test";
import { TranscriptBuffer } from "../abstract/transcript-buffer.js";
import {
  EditableTextareaSurface,
  ReadOnlyNoteSurface,
} from "../implementation/textarea-note-surfaces.js";
import { TranscriptSyncedNote } from "../implementation/transcript-synced-note.js";
import { FakeDocument } from "./_fake-dom.js";

const doc = () => new FakeDocument();

describe("EditableTextareaSurface — the agent message box, unchanged", () => {
  test("is a typeable textarea", () => {
    const surface = new EditableTextareaSurface({ doc: doc() });
    expect(surface.element.tagName).toBe("TEXTAREA");
    expect(surface.element.className).toBe("am-test-input");
    expect(surface.element.readOnly).toBeFalsy();
    expect(surface.editable).toBe(true);
  });

  test("reads and writes its text", () => {
    const surface = new EditableTextareaSurface({ doc: doc() });
    surface.setText("hello");
    expect(surface.getText()).toBe("hello");
    surface.appendText("hello world");
    expect(surface.getText()).toBe("hello world");
  });
});

describe("ReadOnlyNoteSurface — Toyota's note", () => {
  test("is read-only rather than disabled, so notes stay selectable", () => {
    const surface = new ReadOnlyNoteSurface({ doc: doc() });
    expect(surface.element.readOnly).toBe(true);
    expect(surface.element.disabled).toBe(false);
    expect(surface.editable).toBe(false);
  });

  test("renders as white text on a black document", () => {
    const css = new ReadOnlyNoteSurface({ doc: doc() }).element.style.cssText;
    expect(css).toContain("background:#000");
    expect(css).toContain("color:#fff");
  });

  test("still accepts text written to it programmatically", () => {
    const surface = new ReadOnlyNoteSurface({ doc: doc() });
    surface.setText("Today Roy and I worked on the scoreboard");
    expect(surface.getText()).toBe("Today Roy and I worked on the scoreboard");
  });
});

describe("TranscriptSyncedNote", () => {
  test("an external edit is not undone by the next dictated sentence", () => {
    const surface = new ReadOnlyNoteSurface({ doc: doc() });
    const transcript = new TranscriptBuffer({
      onChange: ({ text }) => surface.setText(text),
    });
    const note = new TranscriptSyncedNote({ surface, transcript });

    transcript.accept("Today Roy and I worked on the scoreboard", true);
    expect(note.getText()).toBe("Today Roy and I worked on the scoreboard");

    // Toyota applies "put a period at the end".
    note.setText("Today Roy and I worked on the scoreboard.");

    // The user keeps dictating. Without the resync the period would vanish.
    transcript.accept("Then we went home", true);
    expect(note.getText()).toBe(
      "Today Roy and I worked on the scoreboard. Then we went home",
    );
  });

  test("delegates editability to the surface it wraps", () => {
    const editable = new EditableTextareaSurface({ doc: doc() });
    const readOnly = new ReadOnlyNoteSurface({ doc: doc() });
    const buffer = () => new TranscriptBuffer();
    expect(
      new TranscriptSyncedNote({ surface: editable, transcript: buffer() })
        .editable,
    ).toBe(true);
    expect(
      new TranscriptSyncedNote({ surface: readOnly, transcript: buffer() })
        .editable,
    ).toBe(false);
  });

  test("refuses to build without both collaborators", () => {
    expect(() => new TranscriptSyncedNote({})).toThrow("surface");
    expect(
      () =>
        new TranscriptSyncedNote({
          surface: new ReadOnlyNoteSurface({ doc: doc() }),
        }),
    ).toThrow("transcript buffer");
  });
});
