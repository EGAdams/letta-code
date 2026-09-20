import {
  type AgentEvent,
  AgentEventKind,
  agentEvent,
  ConversationAgent,
  type ConversationTurn,
  TurnCancelledError,
} from "../../../abstract/conversation-agent.interface.js";

export interface ChatTestHttpPort {
  postJSON(
    url: string,
    body: { agent: string; text: string },
  ): Promise<unknown>;
}

export interface TestChatAgentDependencies {
  http: ChatTestHttpPort;
  endpoint?: string;
}

// /api/test deliberately resets an agent's messages before each send. This
// adapter preserves that legacy Chat contract while exposing the same event
// vocabulary as the resumed Letta Code agent used by Input Options.
const REPLY_KINDS = Object.freeze({
  assistant_message: AgentEventKind.ASSISTANT_TEXT,
  send_message: AgentEventKind.ASSISTANT_TEXT,
  reasoning_message: AgentEventKind.REASONING,
  tool_call_message: AgentEventKind.TOOL_CALL,
  tool_return_message: AgentEventKind.TOOL_RESULT,
  error: AgentEventKind.STATUS,
});

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export class TestChatAgentAdapter extends ConversationAgent {
  private readonly http: ChatTestHttpPort;
  private readonly endpoint: string;
  private readonly cancelled = new Set<string>();

  constructor({ http, endpoint = "/api/test" }: TestChatAgentDependencies) {
    super();
    if (!http) throw new Error("TestChatAgentAdapter requires an HttpClient");
    this.http = http;
    this.endpoint = endpoint;
  }

  override async *submit(
    turn: ConversationTurn,
    generationId: string,
  ): AsyncGenerator<AgentEvent, void, unknown> {
    if (!turn?.agent || typeof turn.text !== "string" || !turn.text.trim())
      throw new Error("TestChatAgentAdapter requires an agent and text");
    if (typeof generationId !== "string" || !generationId)
      throw new Error("TestChatAgentAdapter requires a generation id");

    const response = await this.http.postJSON(this.endpoint, {
      agent: turn.agent,
      text: turn.text,
    });
    if (this.cancelled.delete(generationId))
      throw new TurnCancelledError(generationId);
    if (!isRecord(response) || !Array.isArray(response.replies))
      throw new Error("Chat returned invalid replies.");

    for (const row of response.replies) {
      if (
        !isRecord(row) ||
        typeof row.text !== "string" ||
        typeof row.type !== "string" ||
        !Object.hasOwn(REPLY_KINDS, row.type)
      )
        continue;
      const kind = REPLY_KINDS[row.type as keyof typeof REPLY_KINDS];
      const event = agentEvent(kind, row.text, generationId, {
        detail: { replyType: row.type },
      });
      if (event) yield event;
    }
    const terminal = agentEvent(AgentEventKind.TERMINAL, "", generationId);
    if (terminal) yield terminal;
  }

  override cancel(generationId: string): void {
    this.cancelled.add(generationId);
  }
}
