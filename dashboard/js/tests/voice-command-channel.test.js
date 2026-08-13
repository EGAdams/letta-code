import { describe, expect, test } from "bun:test";
import { TranscriptBuffer } from "../abstract/transcript-buffer.js";
import { VoiceCommandChannel } from "../abstract/voice-command-channel.js";

/** A NoteDocument double — the channel only ever uses getText/setText. */
class FakeNote {
  constructor(text = "") {
    this.text = text;
  }
  getText() {
    return this.text;
  }
  setText(next) {
    this.text = next;
  }
}

/** Scripted completeness detector: answers per exact command text. */
class ScriptedDetector {
  constructor(verdicts = {}) {
    this.verdicts = verdicts;
    this.asked = [];
  }
  async assess(text) {
    this.asked.push(text);
    const complete = !!this.verdicts[text];
    return { complete, reason: complete ? "whole instruction" : "trails off" };
  }
}

class ScriptedInterpreter {
  constructor(outcomeFor) {
    this.outcomeFor = outcomeFor;
    this.calls = [];
  }
  async apply(note, command) {
    this.calls.push({ note, command });
    return this.outcomeFor(note, command);
  }
}

function build({ verdicts = {}, outcomeFor, noteText = "" } = {}) {
  const note = new FakeNote(noteText);
  const detector = new ScriptedDetector(verdicts);
  const interpreter = new ScriptedInterpreter(
    outcomeFor ||
      ((n) => ({ kind: "edit", note: `${n}.`, saved: null, message: "" })),
  );
  const statuses = [];
  const commandTexts = [];
  const channel = new VoiceCommandChannel({
    note,
    completenessDetector: detector,
    commandInterpreter: interpreter,
    buffer: new TranscriptBuffer(),
    onCommandText: ({ text }) => commandTexts.push(text),
    onStatus: (message, isError) =>
      statuses.push({ message, isError: !!isError }),
  });
  return { channel, note, detector, interpreter, statuses, commandTexts };
}

describe("VoiceCommandChannel — pausing mid-command", () => {
  test('"Put a" waits, then "period at the end" completes and edits the note', async () => {
    const ctx = build({
      noteText: "Today Roy and I worked on the scoreboard",
      verdicts: { "Put a period at the end": true },
    });

    // The user trails off, then pauses. The recognizer finalizes "Put a".
    await ctx.channel.handleSpeech("Put a", true);
    expect(ctx.detector.asked).toEqual(["Put a"]);
    expect(ctx.interpreter.calls).toEqual([]);
    expect(ctx.note.getText()).toBe("Today Roy and I worked on the scoreboard");

    // Four seconds of silence change nothing — no timer drives this.
    expect(ctx.channel.commandText).toBe("Put a");

    // They carry on. The buffer accumulates rather than starting over.
    await ctx.channel.handleSpeech("period at the end", true);
    expect(ctx.detector.asked).toEqual(["Put a", "Put a period at the end"]);
    expect(ctx.interpreter.calls).toEqual([
      {
        note: "Today Roy and I worked on the scoreboard",
        command: "Put a period at the end",
      },
    ]);
    expect(ctx.note.getText()).toBe(
      "Today Roy and I worked on the scoreboard.",
    );
  });

  test("the command box is emptied once the instruction has run", async () => {
    const ctx = build({ verdicts: { "Put a period at the end": true } });
    await ctx.channel.handleSpeech("Put a", true);
    await ctx.channel.handleSpeech("period at the end", true);
    expect(ctx.channel.commandText).toBe("");
    expect(ctx.commandTexts.at(-1)).toBe("");
  });

  test("interim words are shown but never assessed", async () => {
    const ctx = build();
    await ctx.channel.handleSpeech("Put a per", false);
    expect(ctx.commandTexts.at(-1)).toBe("Put a per");
    expect(ctx.detector.asked).toEqual([]);
  });

  test("the same finalized text is never assessed twice", async () => {
    const ctx = build();
    await ctx.channel.handleSpeech("Put a", true);
    await ctx.channel.handleSpeech("Put a", true);
    expect(ctx.detector.asked).toEqual(["Put a"]);
  });

  test("an incomplete verdict reports why it is waiting", async () => {
    const ctx = build();
    await ctx.channel.handleSpeech("Put a", true);
    expect(ctx.statuses.at(-1)).toEqual({
      message: "Waiting — trails off.",
      isError: false,
    });
  });
});

describe("VoiceCommandChannel — applying commands", () => {
  test("a rejected command leaves both the note and the command text alone", async () => {
    const ctx = build({
      noteText: "Note body",
      verdicts: { "flurb the widget": true },
      outcomeFor: () => ({
        kind: "none",
        note: "Note body",
        saved: null,
        message: "I didn't follow that.",
      }),
    });
    await ctx.channel.handleSpeech("flurb the widget", true);
    expect(ctx.note.getText()).toBe("Note body");
    // Kept so the user can reword and press Run instead of re-dictating.
    expect(ctx.channel.commandText).toBe("flurb the widget");
    expect(ctx.statuses.at(-1)).toEqual({
      message: "I didn't follow that.",
      isError: true,
    });
  });

  test("a save reports where it landed and does not rewrite the note", async () => {
    const ctx = build({
      noteText: "Note body",
      verdicts: { "Save this": true },
      outcomeFor: (note) => ({
        kind: "save",
        note,
        saved: { filename: "2026-08-12_scoreboard.md", path: "/n/x.md" },
        message: "Saved as 2026-08-12_scoreboard.md.",
      }),
    });
    await ctx.channel.handleSpeech("Save this", true);
    expect(ctx.note.getText()).toBe("Note body");
    expect(ctx.statuses.at(-1)).toEqual({
      message: "Saved as 2026-08-12_scoreboard.md.",
      isError: false,
    });
  });

  test("submit() runs a typed command without asking the detector", async () => {
    const ctx = build({ noteText: "Note body" });
    await ctx.channel.submit("  put a period at the end  ");
    expect(ctx.detector.asked).toEqual([]);
    expect(ctx.interpreter.calls).toEqual([
      { note: "Note body", command: "put a period at the end" },
    ]);
    expect(ctx.note.getText()).toBe("Note body.");
  });

  test("submit() with nothing typed reports an error and runs nothing", async () => {
    const ctx = build();
    await ctx.channel.submit("   ");
    expect(ctx.interpreter.calls).toEqual([]);
    expect(ctx.statuses.at(-1)).toEqual({
      message: "Nothing to run.",
      isError: true,
    });
  });

  test("clear() forgets the accumulated command and lets it be re-said", async () => {
    const ctx = build();
    await ctx.channel.handleSpeech("Put a", true);
    ctx.channel.clear();
    expect(ctx.channel.commandText).toBe("");
    await ctx.channel.handleSpeech("Put a", true);
    expect(ctx.detector.asked).toEqual(["Put a", "Put a"]);
  });

  test("a thrown collaborator surfaces as an error and does not wedge the queue", async () => {
    const ctx = build({ noteText: "Body", verdicts: { boom: true } });
    ctx.interpreter.apply = async () => {
      throw new Error("network down");
    };
    await ctx.channel.handleSpeech("boom", true);
    expect(ctx.statuses.at(-1)).toEqual({
      message: "network down",
      isError: true,
    });
    expect(ctx.channel.busy).toBe(false);
  });

  test("queued work never interleaves, so no command is applied twice", async () => {
    // Both fragments land before any interpreter call resolves. The second
    // assessment therefore sees the accumulated "first second" — but the two
    // pieces of work still run strictly one after the other, which is what
    // stops an in-flight edit from racing the next fragment.
    const ctx = build({
      noteText: "n",
      verdicts: { first: true, "first second": true },
    });
    const order = [];
    ctx.interpreter.apply = async (note, command) => {
      order.push(`start:${command}`);
      await Promise.resolve();
      order.push(`end:${command}`);
      return { kind: "edit", note: command, saved: null, message: "" };
    };
    const a = ctx.channel.handleSpeech("first", true);
    const b = ctx.channel.handleSpeech("second", true);
    await Promise.all([a, b]);
    expect(order).toEqual([
      "start:first",
      "end:first",
      "start:first second",
      "end:first second",
    ]);
    expect(ctx.channel.busy).toBe(false);
  });
});

describe("VoiceCommandChannel — construction", () => {
  test("refuses to build without its collaborators", () => {
    expect(() => new VoiceCommandChannel({})).toThrow("NoteDocument");
    expect(() => new VoiceCommandChannel({ note: new FakeNote() })).toThrow(
      "CompletenessDetector",
    );
    expect(
      () =>
        new VoiceCommandChannel({
          note: new FakeNote(),
          completenessDetector: new ScriptedDetector(),
        }),
    ).toThrow("CommandInterpreter");
  });
});
