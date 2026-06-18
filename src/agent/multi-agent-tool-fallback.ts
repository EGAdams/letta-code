import type { LettaStreamingResponse } from "@letta-ai/letta-client/resources/agents/messages";
import type { ApprovalResult } from "./approval-execution";
import { getClient } from "./client";

export type PendingServerToolCall = {
  toolCallId: string;
  toolName: string;
  toolArgs: string;
};

type ServerToolCallInfoLike = {
  toolName: string;
  toolArgs: string;
};

const MULTI_AGENT_TOOL_NAMES = new Set([
  "send_message_to_agent_async",
  "send_message_to_agent_and_wait_for_reply",
]);

// Tools the Letta server streams as tool_call_message + end_turn without executing.
// The client executes these locally and sends results back as a user message.
const CLIENT_SIDE_FALLBACK_TOOLS = new Set(["executor_run"]);

function extractText(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";

  return content
    .map((part) => {
      if (!part || typeof part !== "object") return "";
      const text = (part as { text?: unknown }).text;
      return typeof text === "string" ? text : "";
    })
    .join("");
}

function parseToolArgs(toolArgs: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(toolArgs || "{}");
    return parsed && typeof parsed === "object"
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

type AssistantReplyResult = {
  reply: string;
  runId: string | null;
  stopReason: string | null;
  conversationId: string | null;
  // True when the reply wasn't captured within AGENT_REPLY_TIMEOUT_MS. The
  // message was still delivered (the stream had started) — only the reply is
  // missing — so callers must NOT treat this as a hard failure to retry.
  timedOut?: boolean;
};

export function collectPendingMultiAgentToolCalls(
  serverToolCalls: Map<string, ServerToolCallInfoLike>,
): PendingServerToolCall[] {
  const pending: PendingServerToolCall[] = [];

  for (const [toolCallId, toolInfo] of serverToolCalls) {
    if (
      !MULTI_AGENT_TOOL_NAMES.has(toolInfo.toolName) &&
      !CLIENT_SIDE_FALLBACK_TOOLS.has(toolInfo.toolName)
    )
      continue;
    if (!parseToolArgs(toolInfo.toolArgs)) continue;
    pending.push({
      toolCallId,
      toolName: toolInfo.toolName,
      toolArgs: toolInfo.toolArgs,
    });
  }

  return pending;
}

async function collectAssistantReply(
  stream: AsyncIterable<LettaStreamingResponse>,
): Promise<AssistantReplyResult> {
  let reply = "";
  let runId: string | null = null;
  let stopReason: string | null = null;
  let conversationId: string | null = null;

  for await (const chunk of stream) {
    if ("run_id" in chunk && typeof chunk.run_id === "string") {
      runId = chunk.run_id;
    }
    if (
      "conversation_id" in chunk &&
      typeof chunk.conversation_id === "string"
    ) {
      conversationId = chunk.conversation_id;
    }
    if (chunk.message_type === "assistant_message") {
      reply += extractText(chunk.content);
    } else if (chunk.message_type === "stop_reason") {
      stopReason = chunk.stop_reason ?? null;
    }
  }

  return { reply: reply.trim(), runId, stopReason, conversationId };
}

function buildFallbackRetryMessage(message: string): string {
  return `<system-reminder>
Reply in plain text only.
Do not delegate.
If tools are necessary to answer correctly, you may use them.
Provide a direct final answer (no meta commentary).
</system-reminder>

${message}`;
}

function normalizeForComparison(text: string): string {
  return text.toLowerCase().replace(/\s+/g, " ").trim();
}

function isMetaOrEchoReply(reply: string, originalMessage: string): boolean {
  const normalizedReply = normalizeForComparison(reply);
  const normalizedOriginal = normalizeForComparison(originalMessage);

  if (!normalizedReply) return true;
  if (normalizedReply === normalizedOriginal) return true;
  if (
    normalizedReply.startsWith("**processing user request**") ||
    normalizedReply.startsWith("processing user request")
  ) {
    return true;
  }
  if (
    normalizedReply.startsWith("i need to respond to the user") ||
    normalizedReply.startsWith("i should") ||
    normalizedReply.startsWith("i will")
  ) {
    return true;
  }
  return false;
}

const AGENT_REPLY_TIMEOUT_MS = 90_000;

async function sendMessageToAgentAndCollectReply(
  otherAgentId: string,
  message: string,
): Promise<AssistantReplyResult> {
  const client = await getClient();
  // Send to the target agent's primary message thread instead of a throwaway
  // conversation. Creating a fresh `conversations.create` per call strips the
  // target of its memory and working context; with a broken/slow tool it can
  // then spiral retrying that tool and never emit a reply (stop_reason=
  // max_steps). The empty reply gets reported back as an error, so the sending
  // agent retries the whole delegation in a loop. The agent's main thread has
  // the context it needs to answer directly, usually in a single turn.
  // A stream-creation failure here propagates (genuine "couldn't reach the
  // agent"). Once the stream exists, the message has been delivered, so a slow
  // reply is reported as a timeout sentinel rather than thrown.
  const stream = await client.agents.messages.stream(otherAgentId, {
    messages: [{ role: "user", content: message }],
    stream_tokens: true,
    // Targets that answer do so within a couple of steps; ones that spiral on a
    // broken tool make hundreds. A modest ceiling lets the run end (empty,
    // stop_reason=max_steps) before the wall-clock timeout, so we return a
    // graceful "delivered, reply pending" instead of hanging the full 90s.
    max_steps: 12,
  });

  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<AssistantReplyResult>((resolve) => {
    timer = setTimeout(
      () =>
        resolve({
          reply: "",
          runId: null,
          stopReason: "timeout",
          conversationId: null,
          timedOut: true,
        }),
      AGENT_REPLY_TIMEOUT_MS,
    );
  });

  try {
    return await Promise.race([collectAssistantReply(stream), timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function extractMessageText(content: unknown): string {
  if (typeof content === "string") return content.trim();
  if (!Array.isArray(content)) return "";
  return content
    .map((part) => {
      if (!part || typeof part !== "object") return "";
      const typedPart = part as { text?: unknown };
      return typeof typedPart.text === "string" ? typedPart.text : "";
    })
    .join("")
    .trim();
}

async function recoverAssistantReplyFromHistory(
  runId: string | null,
  conversationId: string | null,
): Promise<string> {
  const client = await getClient();

  if (runId) {
    try {
      const page = await client.runs.messages.list(runId, { limit: 100 });
      const messages = page.getPaginatedItems?.() ?? [];
      for (let i = messages.length - 1; i >= 0; i -= 1) {
        const msg = messages[i];
        if (msg?.message_type !== "assistant_message") continue;
        const text = extractMessageText(msg.content);
        if (text) return text;
      }
    } catch {
      // Fall back to conversation lookup if run messages are unavailable.
    }
  }

  if (conversationId) {
    try {
      const page = await client.conversations.messages.list(conversationId, {
        limit: 100,
      });
      const messages = page.getPaginatedItems?.() ?? [];
      for (let i = messages.length - 1; i >= 0; i -= 1) {
        const msg = messages[i];
        if (msg?.message_type !== "assistant_message") continue;
        const text = extractMessageText(msg.content);
        if (text) return text;
      }
    } catch {
      // Final fallback failed.
    }
  }

  return "";
}

async function executeMultiAgentToolCall(
  call: PendingServerToolCall,
  senderAgentId: string,
): Promise<ApprovalResult> {
  const args = parseToolArgs(call.toolArgs);
  const message = typeof args?.message === "string" ? args.message : "";
  const otherAgentId =
    typeof args?.other_agent_id === "string" ? args.other_agent_id : "";

  if (!message || !otherAgentId) {
    return {
      type: "tool",
      tool_call_id: call.toolCallId,
      status: "error",
      tool_return:
        "Missing required multi-agent tool arguments: message and other_agent_id",
    };
  }

  const client = await getClient();
  const [senderAgent, targetAgent] = await Promise.all([
    client.agents.retrieve(senderAgentId),
    client.agents.retrieve(otherAgentId),
  ]);

  const reminder = `<system-reminder>
This message is from "${senderAgent.name}" (agent ID: ${senderAgentId}), an agent currently running inside the Letta Code CLI (docs.letta.com/letta-code).
The sender will only see the final message you generate (not tool calls or reasoning).
If you need to share detailed information, include it in your response text.
You are the target agent for this request. Answer the user-level request directly.
Do not delegate this request to another agent.
Do not call send_message_to_agent_async or send_message_to_agent_and_wait_for_reply for this request.
Do not ask the sender to provide another agent ID.
</system-reminder>

`;
  const firstAttemptMessage = `${reminder}${message}`;
  let reply: string;
  let runId: string | null;
  let stopReason: string | null;
  let conversationId: string | null;
  let timedOut: boolean;

  try {
    ({
      reply,
      runId,
      stopReason,
      conversationId,
      timedOut = false,
    } = await sendMessageToAgentAndCollectReply(
      otherAgentId,
      firstAttemptMessage,
    ));
  } catch (e) {
    return {
      type: "tool",
      tool_call_id: call.toolCallId,
      status: "error",
      tool_return: `Failed to reach ${otherAgentId}: ${e instanceof Error ? e.message : String(e)}`,
    };
  }

  // Only retry to coax a usable answer out of a meta/echo reply we actually
  // received. Don't retry on a timeout — the target is already slow/spiraling,
  // so a second attempt just doubles the wait and never beats the clock.
  const needsRetry =
    call.toolName === "send_message_to_agent_and_wait_for_reply" &&
    !timedOut &&
    Boolean(reply) &&
    isMetaOrEchoReply(reply, message);

  if (needsRetry) {
    try {
      const retryResult = await sendMessageToAgentAndCollectReply(
        otherAgentId,
        buildFallbackRetryMessage(firstAttemptMessage),
      );
      if (retryResult.reply) {
        reply = retryResult.reply;
        runId = retryResult.runId;
        stopReason = retryResult.stopReason;
        conversationId = retryResult.conversationId;
      }
    } catch {
      // retry timed out; proceed with whatever we have
    }
  }

  if (
    call.toolName === "send_message_to_agent_and_wait_for_reply" &&
    (!reply || isMetaOrEchoReply(reply, message))
  ) {
    reply = await recoverAssistantReplyFromHistory(runId, conversationId);
  }

  if (call.toolName === "send_message_to_agent_async") {
    return {
      type: "tool",
      tool_call_id: call.toolCallId,
      status: "success",
      tool_return: `Message sent to ${targetAgent.name} (${otherAgentId}) in conversation ${conversationId ?? "unknown"}.`,
    };
  }

  if (!reply) {
    // The send itself succeeded — only the reply is missing (e.g. the target
    // hit its step limit before answering). Report this as success, not error,
    // and tell the sender not to resend. A failure status here makes the
    // sending agent retry the same delegation in a loop.
    return {
      type: "tool",
      tool_call_id: call.toolCallId,
      status: "success",
      tool_return: `Message was delivered to ${targetAgent.name} (${otherAgentId}), but it did not return a final reply (run: ${runId ?? "unknown"}, stop_reason: ${stopReason ?? "unknown"}). Do not resend the same message — it was received. Tell the user the request was delivered and a reply is still pending.`,
    };
  }

  return {
    type: "tool",
    tool_call_id: call.toolCallId,
    status: "success",
    tool_return: `${targetAgent.name} replied:\n\n${reply}`,
  };
}

async function executeClientSideTool(
  call: PendingServerToolCall,
): Promise<ApprovalResult> {
  const args = parseToolArgs(call.toolArgs) ?? {};

  if (call.toolName === "executor_run") {
    const command = typeof args.command === "string" ? args.command : "";
    const cwd = typeof args.cwd === "string" ? args.cwd : ".";

    if (!command) {
      return {
        type: "tool",
        tool_call_id: call.toolCallId,
        status: "error",
        tool_return: "executor_run: missing required argument 'command'",
      };
    }

    try {
      const { executor_run } = await import("../tools/impl/Bash");
      const result = await executor_run({ command, cwd });
      const text = result.content.map((c: { text: string }) => c.text).join("");
      return {
        type: "tool",
        tool_call_id: call.toolCallId,
        status: result.status,
        tool_return: text,
      };
    } catch (e) {
      return {
        type: "tool",
        tool_call_id: call.toolCallId,
        status: "error",
        tool_return: `executor_run failed: ${e instanceof Error ? e.message : String(e)}`,
      };
    }
  }

  return {
    type: "tool",
    tool_call_id: call.toolCallId,
    status: "error",
    tool_return: `Unknown client-side fallback tool: ${call.toolName}`,
  };
}

export async function executePendingMultiAgentToolCalls(
  calls: PendingServerToolCall[],
  senderAgentId: string,
): Promise<ApprovalResult[]> {
  const results: ApprovalResult[] = [];
  for (const call of calls) {
    if (CLIENT_SIDE_FALLBACK_TOOLS.has(call.toolName)) {
      results.push(await executeClientSideTool(call));
    } else {
      results.push(await executeMultiAgentToolCall(call, senderAgentId));
    }
  }
  return results;
}
