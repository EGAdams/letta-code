import { describe, expect, test } from "bun:test";
import { AgentEventKind } from "../../../abstract/conversation-agent.interface.js";
import { build } from "./_chat-fixture.ts";

describe("Chat voice session", () => {
  test("uses the conversation port and speaks only current assistant text", async () => {
    const ctx = build([
      { kind: AgentEventKind.REASONING, text: "private thought" },
      { kind: AgentEventKind.TOOL_RESULT, text: "tool secret" },
      { kind: AgentEventKind.ASSISTANT_TEXT, text: "Public answer" },
    ]);
    const sending = ctx.ui.sendText("hello");
    expect(ctx.session.state).toBe("thinking");
    await ctx.entered.promise;
    ctx.release.resolve();
    await sending;
    expect(ctx.spoken).toEqual(["Public answer"]);
    expect(ctx.container.querySelector(".msi-inner").innerHTML).toContain(
      "Public answer",
    );
    expect(ctx.session.state).toBe("listening");
  });

  test("late reply after interruption changes neither transcript nor speaker", async () => {
    const ctx = build([
      { kind: AgentEventKind.ASSISTANT_TEXT, text: "Late answer" },
    ]);
    const sending = ctx.ui.sendText("old question");
    expect(ctx.session.state).toBe("thinking");
    await ctx.entered.promise;
    const generation = ctx.session.currentGeneration;
    ctx.session.interrupt();
    ctx.release.resolve();
    await sending;
    expect(ctx.cancelled).toEqual([]); // navigation owns adapter cancellation
    expect(ctx.spoken).toEqual([]);
    expect(ctx.container.querySelector(".msi-inner").innerHTML).not.toContain(
      "Late answer",
    );
    expect(ctx.session.accepts(generation)).toBe(false);
    expect(ctx.statuses).toEqual(["active"]);
  });

  test("reasoning-only response stays visible but is never spoken", async () => {
    const ctx = build([
      { kind: AgentEventKind.REASONING, text: "internal step" },
    ]);
    const sending = ctx.ui.sendText("status");
    expect(ctx.session.state).toBe("thinking");
    await ctx.entered.promise;
    ctx.release.resolve();
    await sending;
    expect(ctx.spoken).toEqual([]);
    expect(ctx.container.querySelector(".msi-inner").innerHTML).toContain(
      "internal step",
    );
    expect(ctx.session.state).toBe("listening");
  });
});
