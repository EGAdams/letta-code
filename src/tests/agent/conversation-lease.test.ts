import { afterEach, describe, expect, test } from "bun:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  acquireConversationLease,
  ConversationInUseError,
} from "../../agent/conversationLease";

const roots: string[] = [];

function leaseRoot(): string {
  const root = mkdtempSync(join(tmpdir(), "letta-conversation-lease-"));
  roots.push(root);
  return root;
}

afterEach(() => {
  for (const root of roots.splice(0)) {
    rmSync(root, { recursive: true, force: true });
  }
});

describe("conversation lease", () => {
  test("blocks a second live process from sharing one conversation", () => {
    const root = leaseRoot();
    const first = acquireConversationLease({
      agentId: "agent-1",
      conversationId: "conv-1",
      leaseRoot: root,
      pid: 101,
      isProcessAlive: (pid) => pid === 101,
    });

    expect(() =>
      acquireConversationLease({
        agentId: "agent-1",
        conversationId: "conv-1",
        leaseRoot: root,
        pid: 202,
        isProcessAlive: (pid) => pid === 101,
      }),
    ).toThrow(ConversationInUseError);

    first.release();
  });

  test("allows concurrent conversations for the same agent", () => {
    const root = leaseRoot();
    const first = acquireConversationLease({
      agentId: "agent-1",
      conversationId: "conv-1",
      leaseRoot: root,
      pid: 101,
      isProcessAlive: () => true,
    });
    const second = acquireConversationLease({
      agentId: "agent-1",
      conversationId: "conv-2",
      leaseRoot: root,
      pid: 202,
      isProcessAlive: () => true,
    });

    first.release();
    second.release();
  });

  test("allows the same conversation identity on different servers", () => {
    const root = leaseRoot();
    const first = acquireConversationLease({
      agentId: "agent-1",
      conversationId: "default",
      serverUrl: "http://server-a",
      leaseRoot: root,
      pid: 101,
      isProcessAlive: () => true,
    });
    const second = acquireConversationLease({
      agentId: "agent-1",
      conversationId: "default",
      serverUrl: "http://server-b",
      leaseRoot: root,
      pid: 202,
      isProcessAlive: () => true,
    });

    first.release();
    second.release();
  });

  test("reclaims a lease left by a dead process", () => {
    const root = leaseRoot();
    acquireConversationLease({
      agentId: "agent-1",
      conversationId: "conv-1",
      leaseRoot: root,
      pid: 101,
      isProcessAlive: () => false,
    });

    const replacement = acquireConversationLease({
      agentId: "agent-1",
      conversationId: "conv-1",
      leaseRoot: root,
      pid: 202,
      isProcessAlive: () => false,
    });

    replacement.release();
  });
});
