import { describe, expect, test } from "bun:test";
import {
  parseCompletenessDecision,
  parseNoteCommandOutcome,
} from "../abstract/note-command-contracts.js";

describe("parseCompletenessDecision", () => {
  test("passes a well-formed verdict through", () => {
    expect(
      parseCompletenessDecision({ ok: true, complete: true, reason: "whole" }),
    ).toEqual({ complete: true, reason: "whole" });
  });

  test.each([
    ["null", null],
    ["a string", "complete"],
    ["a server error", { ok: false, error: "boom" }],
    ["a non-boolean verdict", { complete: "yes", reason: "x" }],
    ["a missing verdict", { reason: "x" }],
  ])("treats %s as 'not complete yet'", (_label, raw) => {
    expect(parseCompletenessDecision(raw).complete).toBe(false);
  });
});

describe("parseNoteCommandOutcome", () => {
  test("passes an edit through", () => {
    expect(
      parseNoteCommandOutcome(
        { ok: true, kind: "edit", note: "Body.", saved: null, message: "" },
        "Body",
      ),
    ).toEqual({ kind: "edit", note: "Body.", saved: null, message: "" });
  });

  test("passes a save through with its filename", () => {
    const outcome = parseNoteCommandOutcome(
      {
        ok: true,
        kind: "save",
        note: "Body",
        saved: { filename: "n.md", path: "/n.md" },
        message: "Saved as n.md.",
      },
      "Body",
    );
    expect(outcome.kind).toBe("save");
    expect(outcome.saved).toEqual({ filename: "n.md", path: "/n.md" });
  });

  test.each([
    ["null", null],
    ["an unknown kind", { kind: "delete_everything", note: "" }],
    ["a server error", { ok: false, error: "boom" }],
    ["an edit with no text", { kind: "edit", note: "   " }],
  ])("keeps the current note when the reply is %s", (_label, raw) => {
    const outcome = parseNoteCommandOutcome(raw, "Original body");
    expect(outcome.kind).toBe("none");
    expect(outcome.note).toBe("Original body");
    expect(outcome.saved).toBeNull();
  });

  test("surfaces a server error message so the user learns why", () => {
    expect(
      parseNoteCommandOutcome({ ok: false, error: "agent offline" }, "Body")
        .message,
    ).toBe("agent offline");
  });
});
