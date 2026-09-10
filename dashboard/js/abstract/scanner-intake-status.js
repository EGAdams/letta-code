/** Runtime contract for GET /api/scanner-intake-status. */

const TERMINAL_STATUSES = new Set([
  "complete",
  "pass",
  "corrected",
  "fail",
  "stalled",
  "awaiting_vendor_review",
  "needs_human_review",
]);
const LETTA_ID = /^[A-Za-z0-9_-]+$/;

/**
 * @typedef {Object} ScannerIntakeStatus
 * @property {boolean} ok
 * @property {string} status
 * @property {?string} conversationId
 * @property {?number} dispatchedAt
 * @property {boolean} terminal
 * @property {?string} error
 */

/** Parse the HTTP response without allowing a wrong-context fallback. */
export function readScannerIntakeStatus(value) {
  const invalid = {
    ok: false,
    status: "unknown",
    conversationId: null,
    dispatchedAt: null,
    terminal: false,
    error: "scanner intake status was malformed",
  };
  if (typeof value !== "object" || value === null || value.ok !== true) {
    return invalid;
  }
  const status =
    typeof value.status === "string" ? value.status.trim().toLowerCase() : "";
  if (!status) return invalid;
  const conversationId =
    typeof value.conversation_id === "string" &&
    LETTA_ID.test(value.conversation_id)
      ? value.conversation_id
      : null;
  const dispatchedAt =
    typeof value.dispatched_at === "number" &&
    Number.isFinite(value.dispatched_at) &&
    value.dispatched_at > 0
      ? value.dispatched_at
      : null;
  return {
    ok: true,
    status,
    conversationId,
    dispatchedAt,
    terminal: TERMINAL_STATUSES.has(status),
    error: null,
  };
}
