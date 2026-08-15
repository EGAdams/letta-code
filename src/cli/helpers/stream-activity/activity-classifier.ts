import type { StreamActivityKind } from "./ports";

/**
 * Chunk types that prove a tool actually ran. These are the only ones that
 * clear the long no-tool-progress deadline.
 */
const TOOL_PROGRESS_MESSAGE_TYPES: ReadonlySet<string> = new Set([
  "tool_call_message",
  "tool_return_message",
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
  if (TOOL_PROGRESS_MESSAGE_TYPES.has(messageType)) {
    return "tool_progress";
  }
  if (CONTENT_MESSAGE_TYPES.has(messageType)) {
    return "content";
  }
  return null;
}
