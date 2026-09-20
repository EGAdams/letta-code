import {
  type AgentEvent,
  ConversationAgent,
  type ConversationTurn,
} from "../../../abstract/conversation-agent.interface.js";
export interface ChatTestHttpPort {
  postJSON(
    url: string,
    body: {
      agent: string;
      text: string;
    },
  ): Promise<unknown>;
}
export interface TestChatAgentDependencies {
  http: ChatTestHttpPort;
  endpoint?: string;
}
export declare class TestChatAgentAdapter extends ConversationAgent {
  private readonly http;
  private readonly endpoint;
  private readonly cancelled;
  constructor({ http, endpoint }: TestChatAgentDependencies);
  submit(
    turn: ConversationTurn,
    generationId: string,
  ): AsyncGenerator<AgentEvent, void, unknown>;
  cancel(generationId: string): void;
}
