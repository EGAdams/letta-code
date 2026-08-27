import {
  ConversationAgent,
  parseAgentEvent,
  TurnCancelledError,
} from "../abstract/conversation-agent.interface.js";

/**
 * FakeConversationAgent — a first-class adapter, not a test helper.
 *
 * The plan requires that a fake pass the same contract suite as the real
 * adapter (`js/tests/conversation-agent-contract.js`). That is what proves the
 * port is substitutable rather than Letta's HTTP shape wearing an interface,
 * and it is what lets the voice UI be driven end to end with no server.
 *
 * Scripting: pass `events` (a fixed list) or `script` (a function of the turn),
 * each entry being a partial AgentEvent — `{kind, text}`. A `terminal` event is
 * appended if the script does not supply one, because every stream ends.
 */
export class FakeConversationAgent extends ConversationAgent {
  /**
   * @param {object} [options]
   * @param {Array<object>} [options.events]
   * @param {(turn: object) => Array<object>} [options.script]
   * @param {() => Promise<void>} [options.beforeEach]  a hook to interleave
   *   work between events — how a test interrupts mid-stream
   */
  constructor({ events = [], script = null, beforeEach = null } = {}) {
    super();
    this._events = events;
    this._script = script;
    this._beforeEach = beforeEach;
    this._cancelled = new Set();
    /** Every turn this fake was asked to run, for assertions. */
    this.submitted = [];
  }

  async *submit(turn, generationId) {
    this.submitted.push({ turn, generationId });
    const planned = this._script ? this._script(turn) : this._events;
    const withTerminal = planned.some((e) => e?.kind === "terminal")
      ? planned
      : [...planned, { kind: "terminal" }];

    for (const raw of withTerminal) {
      if (this._beforeEach) await this._beforeEach();
      if (this._cancelled.has(generationId)) {
        throw new TurnCancelledError(generationId);
      }
      const event = parseAgentEvent(raw, generationId);
      // Unparseable entries are dropped, exactly as a real adapter drops a
      // malformed frame — a fake that is more forgiving than the real thing
      // hides bugs instead of catching them.
      if (event) yield event;
    }
  }

  cancel(generationId) {
    this._cancelled.add(generationId);
  }

  /** True if cancel() was called for that generation. */
  wasCancelled(generationId) {
    return this._cancelled.has(generationId);
  }
}
