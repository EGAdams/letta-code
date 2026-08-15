import { describe, expect, test } from "bun:test";
import {
  HttpCompletenessDetector,
  HttpNoteCommandInterpreter,
} from "../implementation/http-note-command-services.js";

const httpReturning = (value) => {
  const posts = [];
  return {
    posts,
    postJSON: async (url, body, options) => {
      posts.push({ url, body, options });
      if (value instanceof Error) throw value;
      return value;
    },
  };
};

describe("HttpCompletenessDetector", () => {
  test("posts the accumulated text and returns the verdict", async () => {
    const http = httpReturning({ ok: true, complete: true, reason: "whole" });
    const decision = await new HttpCompletenessDetector({ http }).assess(
      "Put a period at the end",
    );
    expect(http.posts[0].url).toBe("/api/note-command-complete");
    expect(http.posts[0].body).toEqual({ text: "Put a period at the end" });
    expect(decision).toEqual({ complete: true, reason: "whole" });
  });

  test("a dead connection means 'keep waiting', never 'go ahead'", async () => {
    const http = httpReturning(new Error("network down"));
    const decision = await new HttpCompletenessDetector({ http }).assess(
      "Put a",
    );
    expect(decision.complete).toBe(false);
  });

  test("sets its own timeout rather than relying on the client default", async () => {
    const http = httpReturning({ ok: true, complete: false, reason: "" });
    await new HttpCompletenessDetector({ http }).assess("Put a");
    expect(http.posts[0].options.timeout).toBeGreaterThan(0);
  });

  test("refuses to build without an HttpClient", () => {
    expect(() => new HttpCompletenessDetector({})).toThrow("HttpClient");
  });
});

describe("HttpNoteCommandInterpreter", () => {
  test("posts the note plus the command and returns the outcome", async () => {
    const http = httpReturning({
      ok: true,
      kind: "edit",
      note: "Body.",
      saved: null,
      message: "",
    });
    const outcome = await new HttpNoteCommandInterpreter({ http }).apply(
      "Body",
      "put a period at the end",
    );
    expect(http.posts[0].url).toBe("/api/note-command-apply");
    expect(http.posts[0].body).toEqual({
      note: "Body",
      command: "put a period at the end",
    });
    expect(outcome.note).toBe("Body.");
  });

  test("a transport failure leaves the note intact and explains itself", async () => {
    const http = httpReturning(new Error("network down"));
    const outcome = await new HttpNoteCommandInterpreter({ http }).apply(
      "Body",
      "save this",
    );
    expect(outcome.kind).toBe("none");
    expect(outcome.note).toBe("Body");
    expect(outcome.message).toBe("network down");
  });

  test("refuses to build without an HttpClient", () => {
    expect(() => new HttpNoteCommandInterpreter({})).toThrow("HttpClient");
  });
});
