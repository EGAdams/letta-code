import { describe, expect, test } from "bun:test";
import { mergeFinalChunk } from "../abstract/transcript-merge.js";

describe("mergeFinalChunk", () => {
  test("plain append when there is no overlap", () => {
    expect(mergeFinalChunk("hello there", "how are you")).toBe(
      "hello there how are you",
    );
  });

  test("first chunk with nothing committed yet", () => {
    expect(mergeFinalChunk("", "hello there")).toBe("hello there");
    expect(mergeFinalChunk(null, "hello there")).toBe("hello there");
  });

  test("trims an exact single-word restart-boundary repeat", () => {
    expect(mergeFinalChunk("call mazda", "mazda about the invoice")).toBe(
      "call mazda about the invoice",
    );
  });

  test("trims a multi-word restart-boundary repeat", () => {
    expect(
      mergeFinalChunk(
        "please call mazda about",
        "call mazda about the invoice",
      ),
    ).toBe("please call mazda about the invoice");
  });

  test("overlap match is case-insensitive", () => {
    expect(mergeFinalChunk("call Mazda", "mazda now")).toBe("call Mazda now");
  });

  test("a chunk that is entirely a repeat contributes nothing new", () => {
    expect(mergeFinalChunk("call mazda now", "call mazda now")).toBe(
      "call mazda now",
    );
  });

  test("empty new chunk leaves committed text untouched", () => {
    expect(mergeFinalChunk("call mazda", "")).toBe("call mazda");
    expect(mergeFinalChunk("call mazda", "   ")).toBe("call mazda");
  });

  test("no trim when the shared word isn't at the actual boundary", () => {
    // "the" is common to both strings but isn't the tail of `committed` nor
    // the head of `chunk` in a way that lines up — no false match.
    expect(mergeFinalChunk("send the report", "about the invoice")).toBe(
      "send the report about the invoice",
    );
  });
});
