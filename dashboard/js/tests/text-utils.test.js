import { describe, expect, test } from "bun:test";
import { TextUtils } from "../abstract/text-utils.js";

describe("TextUtils.esc", () => {
  test("escapes the four HTML-significant characters", () => {
    expect(TextUtils.esc('<a href="x">&')).toBe(
      "&lt;a href=&quot;x&quot;&gt;&amp;",
    );
  });
  test("null/undefined become empty string", () => {
    expect(TextUtils.esc(null)).toBe("");
    expect(TextUtils.esc(undefined)).toBe("");
  });
  test("numbers are coerced", () => {
    expect(TextUtils.esc(42)).toBe("42");
  });
});

describe("TextUtils.stripMarkdown", () => {
  test("removes emphasis, backticks, headers and trims", () => {
    expect(TextUtils.stripMarkdown("  **bold** `code` #h _i_ >q ")).toBe(
      "bold code h i q",
    );
  });
  test("empty-ish input", () => {
    expect(TextUtils.stripMarkdown(null)).toBe("");
  });
});

describe("TextUtils.splitLeadingHeader", () => {
  test("extracts a leading **Header**", () => {
    expect(TextUtils.splitLeadingHeader("**Thinking** about it")).toEqual({
      header: "Thinking",
      rest: "about it",
    });
  });
  test("no header returns null header and stripped rest", () => {
    expect(TextUtils.splitLeadingHeader("plain **mid** text")).toEqual({
      header: null,
      rest: "plain mid text",
    });
  });
});

describe("TextUtils.sleep", () => {
  test("resolves via injected scheduler", async () => {
    let scheduled = null;
    const fakeScheduler = (fn) => {
      scheduled = fn;
    };
    const p = TextUtils.sleep(999, fakeScheduler);
    expect(scheduled).toBeFunction();
    scheduled(); // fire immediately
    await expect(p).resolves.toBeUndefined();
  });
});
