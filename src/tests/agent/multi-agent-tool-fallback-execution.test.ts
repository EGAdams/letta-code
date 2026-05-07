import { beforeEach, describe, expect, mock, test } from "bun:test";

const createConversationMock = mock(() =>
  Promise.resolve({ id: `conv-${createConversationMock.mock.calls.length}` }),
);

const createMessageMock = mock((_conversationId: string, body: { messages: Array<{ content: string }> }) => {
  const content = body.messages[0]?.content ?? "";

  if (content.includes("Do not use any tools for this answer.")) {
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
});

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
    },
    conversations: {
      create: createConversationMock,
      messages: {
        create: createMessageMock,
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
    createConversationMock.mockClear();
    createMessageMock.mockClear();
    retrieveAgentMock.mockClear();
    getClientMock.mockClear();
  });

  test("retries with a no-tools plain-text reminder when first relay returns meta/non-actionable text", async () => {
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

    expect(createMessageMock).toHaveBeenCalledTimes(2);
    expect(createMessageMock.mock.calls[1]?.[1]).toMatchObject({
      messages: [
        {
          content: expect.stringContaining(
            "Do not use any tools for this answer.",
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
});
