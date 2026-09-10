import { describe, expect, test } from "bun:test";

import { ScannerConversationTerminal } from "../implementation/scanner-conversation-terminal.js";
import { FakeDocument } from "./_fake-dom.js";

const settle = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

function setup() {
  const doc = new FakeDocument();
  const container = doc.createElement("section");
  container.classList.add("hidden");
  const opens = [];
  const sent = [];
  const disposed = [];
  const launcher = {
    open: async (request) => {
      opens.push(request);
      return {
        sendLine: (text) => sent.push(text),
        dispose: () => disposed.push(request.conversationId),
      };
    },
  };
  const terminal = new ScannerConversationTerminal({ launcher, doc });
  return { container, disposed, opens, sent, terminal };
}

describe("ScannerConversationTerminal", () => {
  test("opens the exact scan conversation and sends complete messages", async () => {
    const ctx = setup();
    ctx.terminal.mount(ctx.container, "conv-scan-123");
    await settle();

    expect(ctx.opens).toHaveLength(1);
    expect(ctx.opens[0].conversationId).toBe("conv-scan-123");
    expect(ctx.opens[0].agentId).toBeUndefined();
    expect(ctx.container.querySelector("h2").textContent).toBe(
      "Mazda's Letta Code Terminal",
    );
    const input = ctx.container.querySelector(".mazda-terminal-input");
    input.value = "What happened\nto the total?";
    ctx.container
      .querySelector(".mazda-terminal-controls")
      .querySelector("button")
      .click();

    expect(ctx.sent).toEqual(["What happened to the total?"]);
    expect(input.value).toBe("");
  });

  test("switching scanner conversations disposes the old pty", async () => {
    const ctx = setup();
    const freezerContainer = ctx.container._doc.createElement("section");
    ctx.terminal.mount(ctx.container, "conv-window");
    await settle();
    ctx.terminal.mount(freezerContainer, "conv-freezer");
    await settle();

    expect(ctx.disposed).toContain("conv-window");
    expect(ctx.container.children).toHaveLength(0);
    expect(ctx.container.classList.contains("hidden")).toBe(true);
    expect(ctx.opens.map((request) => request.conversationId)).toEqual([
      "conv-window",
      "conv-freezer",
    ]);
  });

  test("missing identity shows an error and never opens a fallback", async () => {
    const ctx = setup();
    ctx.terminal.mount(ctx.container, null);
    await settle();

    expect(ctx.opens).toHaveLength(0);
    expect(ctx.container.textContent).toContain(
      "no fallback session was opened",
    );
  });
});
