import {
  type AgentEvent,
  AgentEventKind,
  agentEvent,
  ConversationAgent,
  type ConversationTurn,
} from "../../../abstract/conversation-agent.interface.js";
import {
  type BrowserCommand,
  type BrowserOutcome,
  type WorkResult,
  workFrom,
} from "./contracts.js";
import type {
  BrowserWorkspace,
  RequestIdentity,
  Workflows,
} from "./interfaces.js";

/** Decorator: conversation owns speech; tools use the browser/application ports. */
export class OperationalConversationAgent extends ConversationAgent {
  private readonly cancelled = new Set<string>();
  private readonly pending = new Map<string, BrowserCommand>();
  constructor(
    private readonly inner: ConversationAgent,
    private readonly workflows: Workflows,
    private readonly browser: BrowserWorkspace,
    private readonly identities: RequestIdentity,
  ) {
    super();
  }

  override async *submit(
    turn: ConversationTurn,
    generation: string,
  ): AsyncGenerator<AgentEvent> {
    let work: WorkResult | null = null;
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
            let outcome: BrowserOutcome;
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
  override cancel(generation: string): void {
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
