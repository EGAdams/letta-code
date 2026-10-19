import {
  type AgentEvent,
  ConversationAgent,
  type ConversationTurn,
} from "../../../abstract/conversation-agent.interface.js";
import type {
  BrowserWorkspace,
  RequestIdentity,
  Workflows,
} from "./interfaces.js";
/** Decorator: conversation owns speech; tools use the browser/application ports. */
export declare class OperationalConversationAgent extends ConversationAgent {
  private readonly inner;
  private readonly workflows;
  private readonly browser;
  private readonly identities;
  private readonly cancelled;
  private readonly pending;
  constructor(
    inner: ConversationAgent,
    workflows: Workflows,
    browser: BrowserWorkspace,
    identities: RequestIdentity,
  );
  submit(
    turn: ConversationTurn,
    generation: string,
  ): AsyncGenerator<AgentEvent>;
  cancel(generation: string): void;
}
