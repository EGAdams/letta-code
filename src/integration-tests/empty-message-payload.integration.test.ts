import { describe, expect, test } from "bun:test";
import {
  buildConversationMessagesCreateRequestBody,
  hasSendableOutgoingMessages,
} from "../agent/message";
import { buildContentFromQueueBatch } from "../cli/helpers/queuedMessageParts";
import { QueueRuntime } from "../queue/queueRuntime";

function dequeueSingleTaskNotification(text: string) {
  const queue = new QueueRuntime({ maxItems: Infinity });
  queue.enqueue({
    kind: "task_notification",
    source: "task_notification",
    text,
  } as Parameters<typeof queue.enqueue>[0]);
  const batch = queue.consumeItems(1);
  if (!batch) {
    throw new Error("expected queued task notification batch");
  }
  return batch;
}

describe("empty message payload integration guard", () => {
  test("rejects an empty messages array before calling Letta", () => {
    expect(() =>
      buildConversationMessagesCreateRequestBody(
        "default",
        [],
        { agentId: "agent-1", streamTokens: true, background: true },
        [],
      ),
    ).toThrow("Cannot send an empty message payload");
  });

  test("does not treat blank queued notifications as sendable user turns", () => {
    const batch = dequeueSingleTaskNotification("   ");
    const content = buildContentFromQueueBatch(batch);
    const messages = [
      {
        type: "message" as const,
        role: "user" as const,
        content,
      },
    ];

    expect(hasSendableOutgoingMessages(messages)).toBe(false);
    expect(() =>
      buildConversationMessagesCreateRequestBody(
        "default",
        messages,
        { agentId: "agent-1", streamTokens: true, background: true },
        [],
      ),
    ).toThrow("Cannot send an empty message payload");
  });

  test("keeps non-empty reflection completion notifications sendable", () => {
    const batch = dequeueSingleTaskNotification(
      "Reflected on /palace, the halls remember more now.",
    );
    const content = buildContentFromQueueBatch(batch);
    const messages = [
      {
        type: "message" as const,
        role: "user" as const,
        content,
      },
    ];

    expect(hasSendableOutgoingMessages(messages)).toBe(true);
    const body = buildConversationMessagesCreateRequestBody(
      "default",
      messages,
      { agentId: "agent-1", streamTokens: true, background: true },
      [],
    );
    expect(body.messages).toHaveLength(1);
  });
});
