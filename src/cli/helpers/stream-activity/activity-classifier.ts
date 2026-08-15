import type { StreamActivityKind } from "./ports";

/**
 * Chunk types that prove a tool actually ran. These are the only ones that
 * clear the long no-tool-progress deadline.
 *
 * The call and the return are kept distinct because the gap between them is
 * legitimate silence — the tool is executing — and must not count against the
 * short no-content deadline.
 */
const TOOL_MESSAGE_TYPES: ReadonlyMap<string, StreamActivityKind> = new Map([
  ["tool_call_message", "tool_started" as const],
  ["tool_return_message", "tool_finished" as const],
]);

/**
 * Chunk types that prove the model is alive and producing output. They clear
 * the short no-content deadline but not the tool-progress one.
 *
 * `ping` is deliberately absent: pings keep the HTTP connection open without
 * the model producing anything, which is exactly the hang this guards against.
 * `stop_reason` and `usage_statistics` are bookkeeping, not progress.
 */
const CONTENT_MESSAGE_TYPES: ReadonlySet<string> = new Set([
  "reasoning_message",
  "assistant_message",
  "hidden_reasoning_message",
  "approval_request_message",
  "system_message",
  "user_message",
]);

/**
 * Classify one stream chunk. Adding a message type is a table edit here rather
 * than another branch in the drain loop (OCP).
 *
 * @returns the liveness the chunk proves, or null if it proves nothing.
 */
export function classifyStreamActivity(
  messageType: string | undefined,
): StreamActivityKind | null {
  if (!messageType) {
    return null;
  }
  const toolKind = TOOL_MESSAGE_TYPES.get(messageType);
  if (toolKind) {
    return toolKind;
  }
  if (CONTENT_MESSAGE_TYPES.has(messageType)) {
    return "content";
  }
  return null;
}
