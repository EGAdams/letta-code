import {
  AgentEventKind,
  agentEvent,
  ConversationAgent,
} from "../../../abstract/conversation-agent.interface.js";
import { workFrom } from "./contracts.js";
/** Decorator: conversation owns speech; tools use the browser/application ports. */
export class OperationalConversationAgent extends ConversationAgent {
  inner;
  workflows;
  browser;
  identities;
  cancelled = new Set();
  pending = new Map();
  constructor(inner, workflows, browser, identities) {
    super();
    this.inner = inner;
    this.workflows = workflows;
    this.browser = browser;
    this.identities = identities;
  }
  async *submit(turn, generation) {
    let work = null;
    try {
      for await (const event of this.inner.submit(
        {
          ...turn,
          requestId:
            turn.requestId || this.identities.forGeneration(generation),
        },
        generation,
      )) {
        if (
          event.kind === AgentEventKind.TOOL_RESULT &&
          event.name === "receptionist_work"
        ) {
          work = workFrom(event.detail?.work);
          if (work) this.browser.show(work.state);
          if (work?.state.command)
            this.pending.set(generation, work.state.command);
          yield event;
          continue;
        }
        if (
          event.kind === AgentEventKind.TERMINAL &&
          work?.state.command &&
          !this.cancelled.has(generation)
        ) {
          const command = work.state.command;
          if (await this.workflows.claim(command)) {
            if (this.cancelled.has(generation)) continue;
            let outcome;
            try {
              outcome = await this.browser.execute(command);
            } catch (error) {
              outcome = { ok: false, error: String(error) };
            }
            const verified = await this.workflows.verify(command, outcome);
            this.browser.show(verified.state);
            if (!this.cancelled.has(generation)) {
              const reply = agentEvent(
                AgentEventKind.ASSISTANT_TEXT,
                verified.ok ? verified.state.message : verified.error,
                generation,
              );
              if (reply) yield reply;
            }
          }
        }
        yield event;
      }
    } finally {
      this.pending.delete(generation);
      this.cancelled.delete(generation);
    }
  }
  cancel(generation) {
    this.cancelled.add(generation);
    this.inner.cancel(generation);
    const command = this.pending.get(generation);
    if (command)
      void this.workflows
        .cancel(command)
        .then((work) => this.browser.show(work.state))
        .catch(() => {});
  }
}
