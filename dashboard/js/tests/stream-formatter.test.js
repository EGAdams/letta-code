import { describe, expect, test } from "bun:test";
import {
  AgentStreamFormatter,
  StreamFormatter,
} from "../abstract/stream-formatter.interface.js";

describe("StreamFormatter (Strategy base)", () => {
  test("abstract formatRow throws", () => {
    expect(() => new StreamFormatter().formatRow({})).toThrow(
      /formatRow\(\) is abstract/,
    );
  });

  test("keyFor builds a stable dedup key", () => {
    const k = new AgentStreamFormatter().keyFor({
      date: "2026-06-07T10:00:00",
      type: "reasoning_message",
      text: "hello",
    });
    expect(k).toBe("2026-06-07T10:00:00|reasoning_message|hello");
  });
});

describe("AgentStreamFormatter (concrete Strategy)", () => {
  const f = new AgentStreamFormatter();

  test("formats a leading **Header** into a .hdr span", () => {
    const html = f.formatRow({
      date: "2026-06-07T10:11:12",
      type: "assistant_message",
      text: "**Plan** do the thing",
    });
    expect(html).toContain(
      '<span class="msi-stamp">[2026-06-07 10:11:12]</span>',
    );
    expect(html).toContain('<span class="hdr">Plan</span> do the thing');
  });

  test("falls back to the type as header when no markdown header", () => {
    const html = f.formatRow({
      date: "2026-06-07T00:00:00",
      type: "tool_call_message",
      text: "running ls",
    });
    expect(html).toContain('<span class="hdr">tool_call</span> running ls');
  });

  test("escapes HTML in the body", () => {
    const html = f.formatRow({
      date: "",
      type: "",
      text: "<script>x</script>",
    });
    expect(html).toContain("&lt;script&gt;x&lt;/script&gt;");
    expect(html).not.toContain("<script>x");
  });
});
