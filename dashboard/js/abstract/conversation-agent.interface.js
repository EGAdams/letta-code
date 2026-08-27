import { abstractMethod } from "./not-implemented.js";

/**
 * IConversationAgent — the port for "something that can hold a conversation".
 *
 * Documented as Planned on Project Plans -> Voice Communication ->
 * IConversationAgent. Today `InputOptionsRenderer.send()` POSTs
 * `/api/letta-code-message` itself, so high-level UI policy imports a
 * Letta-shaped HTTP call and no other engine can be substituted. This contract
 * is what removes that dependency: policy talks to `ConversationAgent`, and
 * LettaAgentAdapter / FakeConversationAgent / a future local model all satisfy
 * it identically.
 *
 * It also draws a line the renderers currently redraw by hand every time:
 * **public assistant text is not the same thing as reasoning, tool calls, tool
 * results or status.** Only the first is speakable, and that is a property of
 * the event kind, not of whichever renderer happens to receive it.
 *
 * @typedef {object} ConversationTurn
 * @property {string} agent            agent id the turn is addressed to
 * @property {string} text             what the user said or typed
 * @property {string|null} [conversationId]  resume key, when one is known
 *
 * @typedef {object} AgentEvent
 * @property {string} kind             one of AgentEventKind
 * @property {string} text             may be empty for non-text kinds
 * @property {string} generationId     the turn this event belongs to
 * @property {string} [name]           tool name, for tool_call / tool_result
 * @property {object|null} [detail]    adapter-specific extras, never spoken
 */

/** The event vocabulary. Anything outside it is dropped, not guessed at. */
export const AgentEventKind = Object.freeze({
  ASSISTANT_TEXT: "assistant_text",
  REASONING: "reasoning",
  TOOL_CALL: "tool_call",
  TOOL_RESULT: "tool_result",
  STATUS: "status",
  TERMINAL: "terminal",
});

/**
 * The one kind that may reach a speech synthesizer.
 *
 * Kept beside the vocabulary rather than inside SpokenOutputPolicy so that
 * adding a kind forces a decision about speakability in the same edit.
 */
export const SPEAKABLE_KINDS = Object.freeze(
  new Set([AgentEventKind.ASSISTANT_TEXT]),
);

const KINDS = new Set(Object.values(AgentEventKind));

/** True if this kind is safe to speak aloud. Unknown kinds are never spoken. */
export function isSpeakable(kind) {
  return SPEAKABLE_KINDS.has(kind);
}

/**
 * Normalise one event coming out of an adapter, failing closed.
 *
 * Adapters parse replies from a network, so their output is untrusted in the
 * same way the note-command replies are (see `note-command-contracts.js`). An
 * unrecognisable event is `null` — dropped — never a `status` event with a
 * guessed body and never a speakable one.
 *
 * @param {unknown} raw
 * @param {string} generationId
 * @returns {AgentEvent|null}
 */
export function parseAgentEvent(raw, generationId) {
  if (!raw || typeof raw !== "object") return null;
  if (!KINDS.has(raw.kind)) return null;
  if (typeof generationId !== "string" || !generationId) return null;
  const text = typeof raw.text === "string" ? raw.text : "";
  // Speakable means it will be read out loud; an empty one is noise, and a
  // blank utterance is worse than silence.
  if (raw.kind === AgentEventKind.ASSISTANT_TEXT && !text.trim()) return null;
  const event = { kind: raw.kind, text, generationId };
  if (typeof raw.name === "string" && raw.name) event.name = raw.name;
  if (raw.detail && typeof raw.detail === "object") event.detail = raw.detail;
  return event;
}

/** Convenience constructor for adapters building their own events. */
export function agentEvent(kind, text = "", generationId, extra = {}) {
  return parseAgentEvent({ kind, text, ...extra }, generationId);
}

/** Thrown by an adapter when a turn is cancelled while still in flight. */
export class TurnCancelledError extends Error {
  constructor(generationId) {
    super(`conversation turn ${generationId} was cancelled`);
    this.name = "TurnCancelledError";
    this.generationId = generationId;
  }
}

/**
 * The port itself.
 *
 * `submit` is an async generator so a streaming adapter and a
 * request/response one present the same shape: the non-streaming Letta path
 * simply yields two events at the end instead of many along the way. Callers
 * write one loop either way, which is what makes the adapters substitutable.
 */
export class ConversationAgent {
  /**
   * @param {ConversationTurn} _turn
   * @param {string} _generationId
   * @returns {AsyncGenerator<AgentEvent>}
   */
  // biome-ignore lint/correctness/useYield: abstract primitive — subclasses yield
  async *submit(_turn, _generationId) {
    abstractMethod("ConversationAgent.submit");
  }

  /**
   * Abandon a turn by generation id.
   *
   * Must be safe to call for a generation that already finished, was never
   * submitted, or was cancelled before — cancellation races with completion by
   * nature, and a caller cannot be asked to win that race first.
   *
   * @param {string} _generationId
   */
  cancel(_generationId) {
    abstractMethod("ConversationAgent.cancel");
  }
}
