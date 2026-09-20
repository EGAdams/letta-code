import { describe, expect, test } from "bun:test";
import { AgentEventKind } from "../../../abstract/conversation-agent.interface.js";
import { build, deferred } from "./_chat-fixture.ts";

describe("Chat playback", () => {
  test("active playback belongs to session until audio ends", async () => {
    const finished = deferred();
    let cancels = 0;
    const ctx = build(
      [{ kind: AgentEventKind.ASSISTANT_TEXT, text: "Answer" }],
      {
        supported: true,
        speak: () => ({
          pending: Promise.resolve("edge-tts"),
          finished: finished.promise,
          cancel: () => {
            cancels += 1;
            finished.resolve();
          },
        }),
        cancel() {},
      },
    );
    const sending = ctx.ui.sendText("question");
    expect(ctx.session.state).toBe("thinking");
    await ctx.entered.promise;
    ctx.release.resolve();
    await sending;
    expect(ctx.session.state).toBe("speaking");
    ctx.session.interrupt();
    expect(cancels).toBe(1);
    expect(ctx.session.state).toBe("interrupted");
  });

  test("audio ending normally returns the session to listening", async () => {
    const finished = deferred();
    const ctx = build(
      [{ kind: AgentEventKind.ASSISTANT_TEXT, text: "Answer" }],
      {
        supported: true,
        speak: () => ({
          pending: Promise.resolve("edge-tts"),
          finished: finished.promise,
          cancel() {},
        }),
        cancel() {},
      },
    );
    const sending = ctx.ui.sendText("question");
    await ctx.entered.promise;
    ctx.release.resolve();
    await sending;
    expect(ctx.session.state).toBe("speaking");
    finished.resolve();
    await finished.promise;
    await Promise.resolve();
    expect(ctx.session.state).toBe("listening");
  });

  test("a new Send stops the previous answer while starting a new turn", async () => {
    const finished = [deferred(), deferred()];
    const cancelled: number[] = [];
    let calls = 0;
    const ctx = build(
      [{ kind: AgentEventKind.ASSISTANT_TEXT, text: "Answer" }],
      {
        supported: true,
        speak: () => {
          const index = calls++;
          return {
            pending: Promise.resolve("edge-tts"),
            finished: finished[index].promise,
            cancel: () => {
              cancelled.push(index);
              finished[index].resolve();
            },
          };
        },
        cancel() {},
      },
    );
    const first = ctx.ui.sendText("first");
    await ctx.entered.promise;
    ctx.release.resolve();
    await first;
    await ctx.ui.sendText("second");
    expect(cancelled).toEqual([0]);
    expect(ctx.session.state).toBe("speaking");
    finished[1].resolve();
  });

  test("turning Speak off cancels only its current playback", async () => {
    const finished = deferred();
    let cancels = 0;
    const ctx = build(
      [{ kind: AgentEventKind.ASSISTANT_TEXT, text: "Answer" }],
      {
        supported: true,
        speak: () => ({
          pending: Promise.resolve("edge-tts"),
          finished: finished.promise,
          cancel: () => {
            cancels += 1;
            finished.resolve();
          },
        }),
        cancel() {
          throw new Error("global cancel should not be used");
        },
      },
    );
    const sending = ctx.ui.sendText("question");
    await ctx.entered.promise;
    ctx.release.resolve();
    await sending;
    ctx.container.querySelector(".am-speak").click();
    expect(cancels).toBe(1);
    expect(ctx.session.state).toBe("interrupted");
  });

  test("starting microphone capture stops active playback", async () => {
    const finished = deferred();
    let cancels = 0;
    const ctx = build(
      [{ kind: AgentEventKind.ASSISTANT_TEXT, text: "Answer" }],
      {
        supported: true,
        speak: () => ({
          pending: Promise.resolve("edge-tts"),
          finished: finished.promise,
          cancel: () => {
            cancels += 1;
            finished.resolve();
          },
        }),
        cancel() {},
      },
    );
    const sending = ctx.ui.sendText("question");
    expect(ctx.session.state).toBe("thinking");
    await ctx.entered.promise;
    ctx.release.resolve();
    await sending;
    const voice = ctx.container.querySelector(".voice-btn");
    await voice._listeners.click[0]();
    expect(cancels).toBe(1);
    expect(ctx.session.state).toBe("interrupted");
  });
});
