import { describe, expect, test } from "bun:test";

import {
  buildTerminalQuery,
  isTerminalSession,
  TerminalLauncher,
} from "../abstract/terminal-launcher.interface.js";

describe("TerminalLauncher interface", () => {
  test("requires a concrete open implementation", async () => {
    await expect(new TerminalLauncher().open({})).rejects.toThrow(/abstract/);
  });

  test("accepts only the narrow terminal session port", () => {
    expect(isTerminalSession({ dispose() {}, sendLine(_text) {} })).toBe(true);
    expect(isTerminalSession({ dispose() {} })).toBe(false);
    expect(isTerminalSession(null)).toBe(false);
  });

  test("conversation identity takes precedence in the socket query", () => {
    const query = buildTerminalQuery({
      cols: 100,
      rows: 30,
      agentId: "agent-mazda",
      conversationId: "conv-scan-123",
    });

    expect(query).toContain("conversation=conv-scan-123");
    expect(query).not.toContain("agent=");
  });
});
