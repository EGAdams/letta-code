import { abstractMethod } from "./not-implemented.js";

/**
 * @typedef {Object} TerminalOpenRequest
 * @property {Element} hostEl
 * @property {?string} [agentId]
 * @property {?string} [conversationId]
 * @property {Document} [doc]
 * @property {(message:string, isError?:boolean) => void} [onStatus]
 */

/**
 * TerminalLauncher — Abstract Factory for a browser terminal session.
 *
 * Callers choose the Letta target and own the surrounding controls; concrete
 * launchers own xterm, WebSocket, resize, and teardown details.
 */
export class TerminalLauncher {
  /** @param {TerminalOpenRequest} _request */
  async open(_request) {
    abstractMethod("open");
  }
}

/** Build the one WebSocket query shape shared by every terminal surface. */
export function buildTerminalQuery({
  cols,
  rows,
  agentId = null,
  conversationId = null,
}) {
  const params = new URLSearchParams({
    cols: String(cols),
    rows: String(rows),
  });
  if (conversationId) params.set("conversation", conversationId);
  else if (agentId) params.set("agent", agentId);
  return params.toString();
}

/** Fail closed when a launcher returns something other than the small port. */
export function isTerminalSession(value) {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof value.dispose === "function" &&
    typeof value.sendLine === "function"
  );
}
