import {
  AgentEventKind,
  agentEvent,
  ConversationAgent,
  TurnCancelledError,
} from "../abstract/conversation-agent.interface.js";

/**
 * LettaAgentAdapter — the first IConversationAgent, over the endpoint the
 * renderers call today.
 *
 * It exists to move three transport facts out of UI code, where they have no
 * business being:
 *
 *  - **the 930s timeout.** `run_letta_code_message` gets a 900s server budget
 *    because a real Mazda turn can run for minutes; the client default is 30s,
 *    so without the override the browser aborts an answer the backend goes on
 *    to produce. Every caller currently has to remember that number.
 *  - **conversation resume.** The reply carries `run.conversation_id`, and the
 *    next turn must send it back or the CLI silently starts a fresh session.
 *  - **the reply shape.** `{ ok, reply }`, with `ok: false` carrying `error`.
 *
 * It is request/response, not streaming — the endpoint returns one lump — so a
 * turn yields `assistant_text` then `terminal`. Callers still write the same
 * loop they would write for a streaming adapter, which is the point of the
 * port: replacing this with a streaming engine changes no caller.
 */

/** The server-side budget for one turn, plus headroom. */
export const LETTA_TURN_TIMEOUT_MS = 930000;

export class LettaAgentAdapter extends ConversationAgent {
  /**
   * @param {object} deps
   * @param {import("../abstract/http-client.interface.js").HttpClient} deps.http
   * @param {Storage} [deps.storage]  where conversation ids are remembered;
   *   omit it and every turn starts a fresh conversation
   * @param {string} [deps.endpoint]
   * @param {number} [deps.timeout]
   */
  constructor({
    http,
    storage = null,
    endpoint = "/api/letta-code-message",
    timeout = LETTA_TURN_TIMEOUT_MS,
  }) {
    super();
    if (!http) throw new Error("LettaAgentAdapter requires an HttpClient");
    this._http = http;
    this._storage = storage;
    this._endpoint = endpoint;
    this._timeout = timeout;
    this._cancelled = new Set();
  }

  async *submit(turn, generationId) {
    const text = typeof turn?.text === "string" ? turn.text : "";
    if (!text.trim()) throw new Error("LettaAgentAdapter: nothing to send");
    const agent = turn?.agent;
    if (!agent) throw new Error("LettaAgentAdapter: turn needs an agent id");

    const conversationId =
      turn.conversationId ?? this._readConversationId(agent);
    const reply = await this._http.postJSON(
      this._endpoint,
      { agent, text, conversation_id: conversationId },
      { timeout: this._timeout },
    );

    // Cancellation is checked after the await, not before: the request is
    // already gone, so all we can honour is "do not deliver the result". That
    // is exactly the fence VoiceSession draws, applied at the adapter edge.
    if (this._cancelled.has(generationId)) {
      this._cancelled.delete(generationId);
      throw new TurnCancelledError(generationId);
    }

    if (!reply?.ok || !reply.reply) {
      throw new Error(reply?.error || "Mazda returned no answer.");
    }
    this._rememberConversationId(agent, reply.run?.conversation_id);

    yield agentEvent(AgentEventKind.ASSISTANT_TEXT, reply.reply, generationId);
    yield agentEvent(AgentEventKind.TERMINAL, "", generationId, {
      detail: { conversationId: reply.run?.conversation_id ?? null },
    });
  }

  /**
   * There is no server-side cancel for this endpoint, so cancellation is
   * delivery-side only. Saying so plainly here is better than a method that
   * looks like it stops work and does not.
   */
  cancel(generationId) {
    this._cancelled.add(generationId);
  }

  /** @private */
  _key(agent) {
    return `msi-conv-${agent}`;
  }

  /** @private */
  _readConversationId(agent) {
    return this._storage?.getItem?.(this._key(agent)) || null;
  }

  /** @private */
  _rememberConversationId(agent, conversationId) {
    if (!conversationId || !this._storage?.setItem) return;
    this._storage.setItem(this._key(agent), conversationId);
  }
}
