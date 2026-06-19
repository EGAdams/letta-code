import { describe, expect, test } from "bun:test";
import { collectPendingMultiAgentToolCalls } from "../../agent/multi-agent-tool-fallback";

describe("multi-agent tool fallback", () => {
  test("collects complete pending multi-agent server tool calls", () => {
    const calls = collectPendingMultiAgentToolCalls(
      new Map([
        [
          "call-1",
          {
            toolName: "send_message_to_agent_and_wait_for_reply",
            toolArgs: '{"message":"status?","other_agent_id":"agent-target"}',
          },
        ],
        [
          "call-2",
          {
            toolName: "run_claude_code_sdk",
            toolArgs:
              '{"task":"inspect receipts","working_dir":"/home/adamsl/rol_finances"}',
          },
        ],
        [
          "call-3",
          {
            toolName: "web_search_exa",
            toolArgs: '{"query":"ignored"}',
          },
        ],
      ]),
    );

    expect(calls).toEqual([
      {
        toolCallId: "call-1",
        toolName: "send_message_to_agent_and_wait_for_reply",
        toolArgs: '{"message":"status?","other_agent_id":"agent-target"}',
      },
      {
        toolCallId: "call-2",
        toolName: "run_claude_code_sdk",
        toolArgs:
          '{"task":"inspect receipts","working_dir":"/home/adamsl/rol_finances"}',
      },
    ]);
  });

  test("ignores incomplete streamed JSON arguments", () => {
    const calls = collectPendingMultiAgentToolCalls(
      new Map([
        [
          "call-1",
          {
            toolName: "send_message_to_agent_and_wait_for_reply",
            toolArgs: '{"message":"status?"',
          },
        ],
      ]),
    );

    expect(calls).toEqual([]);
  });
});
