import { describe, expect, test } from "bun:test";
import { TurnCancelledError } from "../../../abstract/conversation-agent.interface.js";
import { StreamingLettaAgentAdapter } from "../src/streaming-letta-agent-adapter.ts";

const encoder = new TextEncoder();

function responseFromChunks(chunks: string[]): Response {
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    }),
    { headers: { "Content-Type": "application/x-ndjson" } },
  );
}

describe("StreamingLettaAgentAdapter", () => {
  test("parses fragmented NDJSON and yields assistant deltas before terminal", async () => {
    const storage = new Map<string, string>();
    const first = JSON.stringify({
      type: "event",
      event: {
        type: "stream_event",
        event: { message_type: "assistant_message", content: "Hello. " },
      },
    });
    const terminal = JSON.stringify({
      type: "event",
      event: {
        type: "result",
        result: "Hello.",
        conversation_id: "conv-123",
      },
    });
    const agent = new StreamingLettaAgentAdapter({
      storage: {
        getItem: (key) => storage.get(key) ?? null,
        setItem: (key, value) => storage.set(key, value),
      },
      fetchFn: async () =>
        responseFromChunks([
          `${first.slice(0, 17)}`,
          `${first.slice(17)}\n${terminal}\n`,
        ]),
    });
    const events = [];
    for await (const event of agent.submit(
      { agent: "agent-toyota", text: "hello" },
      "gen-1",
    ))
      events.push(event);

    expect(events.map((event) => [event.kind, event.text])).toEqual([
      ["assistant_text", "Hello. "],
      ["terminal", ""],
    ]);
    expect(storage.get("msi-conv-agent-toyota")).toBe("conv-123");
  });

  test("malformed records fail closed", async () => {
    const agent = new StreamingLettaAgentAdapter({
      fetchFn: async () => responseFromChunks(["{bad json}\n"]),
    });
    const next = agent
      .submit({ agent: "agent-toyota", text: "hello" }, "gen-bad")
      .next();
    expect(next).rejects.toThrow("malformed JSON");
  });

  test("cancel aborts the request and rejects as a cancelled turn", async () => {
    let signal!: AbortSignal;
    const agent = new StreamingLettaAgentAdapter({
      fetchFn: (_url, init) => {
        signal = init?.signal as AbortSignal;
        return new Promise((_resolve, reject) => {
          signal.addEventListener("abort", () => reject(signal.reason));
        });
      },
    });
    const next = agent
      .submit({ agent: "agent-toyota", text: "hello" }, "gen-cancel")
      .next();
    await Promise.resolve();
    agent.cancel("gen-cancel");
    expect(next).rejects.toBeInstanceOf(TurnCancelledError);
  });
});
