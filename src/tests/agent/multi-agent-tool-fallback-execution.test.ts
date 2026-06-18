import { beforeEach, describe, expect, mock, test } from "bun:test";

// The fallback now messages the target agent's primary thread via
// client.agents.messages.stream(agentId, body) instead of creating a throwaway
// conversation. The first arg is the target agent id; the second is the body.
const streamMessageMock = mock(
  (_agentId: string, body: { messages: Array<{ content: string }> }) => {
    const content = body.messages[0]?.content ?? "";

    if (
      content.includes(
        "If tools are necessary to answer correctly, you may use them.",
      )
    ) {
      return Promise.resolve({
        async *[Symbol.asyncIterator]() {
          yield {
            message_type: "assistant_message",
            content: "Retry reply from Hailey",
            run_id: "run-retry-success",
          };
          yield {
            message_type: "stop_reason",
            stop_reason: "end_turn",
          };
        },
      });
    }

    return Promise.resolve({
      async *[Symbol.asyncIterator]() {
        yield {
          message_type: "assistant_message",
          content:
            "**Processing user request**\n\nI need to respond to the user by messaging Hailey.",
          run_id: "run-first-meta",
        };
        yield {
          message_type: "stop_reason",
          stop_reason: "end_turn",
        };
      },
    });
  },
);

const retrieveAgentMock = mock((agentId: string) =>
  Promise.resolve({
    id: agentId,
    name: agentId === "agent-sender" ? "Scissari" : "Hailey",
  }),
);

const getClientMock = mock(() =>
  Promise.resolve({
    agents: {
      retrieve: retrieveAgentMock,
      messages: {
        stream: streamMessageMock,
      },
    },
  }),
);

mock.module("../../agent/client", () => ({
  getClient: getClientMock,
  getServerUrl: () => "http://localhost:8283",
  clearLastSDKDiagnostic: () => {},
  consumeLastSDKDiagnostic: () => null,
}));

const { executePendingMultiAgentToolCalls } = await import(
  "../../agent/multi-agent-tool-fallback"
);

describe("multi-agent tool fallback execution", () => {
  beforeEach(() => {
    streamMessageMock.mockClear();
    retrieveAgentMock.mockClear();
    getClientMock.mockClear();
  });

  test("retries with a plain-text direct-answer reminder when first relay returns meta/non-actionable text", async () => {
    const results = await executePendingMultiAgentToolCalls(
      [
        {
          toolCallId: "call-1",
          toolName: "send_message_to_agent_and_wait_for_reply",
          toolArgs:
            '{"message":"How is the finance report going?","other_agent_id":"agent-target"}',
        },
      ],
      "agent-sender",
    );

    expect(streamMessageMock).toHaveBeenCalledTimes(2);
    // Both sends target the same agent's main thread (first arg = agent id).
    expect(streamMessageMock.mock.calls[0]?.[0]).toBe("agent-target");
    expect(streamMessageMock.mock.calls[1]?.[0]).toBe("agent-target");
    expect(streamMessageMock.mock.calls[1]?.[1]).toMatchObject({
      messages: [
        {
          content: expect.stringContaining(
            "If tools are necessary to answer correctly, you may use them.",
          ),
        },
      ],
    });
    expect(results).toEqual([
      {
        type: "tool",
        tool_call_id: "call-1",
        status: "success",
        tool_return: "Hailey replied:\n\nRetry reply from Hailey",
      },
    ]);
  });

  test("returns a non-retry success (not error) when the target delivers no reply, and does not resend", async () => {
    // Stream ends with a stop_reason but no assistant_message (target spiraled
    // on a tool / hit its step limit). The send still succeeded, so we must NOT
    // report an error — a failure status makes the sender loop on the same call.
    streamMessageMock.mockImplementationOnce(() =>
      Promise.resolve({
        async *[Symbol.asyncIterator]() {
          yield { message_type: "stop_reason", stop_reason: "max_steps" };
        },
      }),
    );

    const results = await executePendingMultiAgentToolCalls(
      [
        {
          toolCallId: "call-noreply",
          toolName: "send_message_to_agent_and_wait_for_reply",
          toolArgs:
            '{"message":"Publish the dashboard please","other_agent_id":"agent-target"}',
        },
      ],
      "agent-sender",
    );

    // Exactly one send — no retry storm on a no-reply result.
    expect(streamMessageMock).toHaveBeenCalledTimes(1);
    expect(results).toEqual([
      expect.objectContaining({
        type: "tool",
        tool_call_id: "call-noreply",
        status: "success",
        tool_return: expect.stringContaining("did not return a final reply"),
      }),
    ]);
    expect((results[0] as { tool_return: string }).tool_return).toContain(
      "Do not resend",
    );
  });
});
