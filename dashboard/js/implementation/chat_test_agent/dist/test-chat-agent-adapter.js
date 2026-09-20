import {
  AgentEventKind,
  agentEvent,
  ConversationAgent,
  TurnCancelledError,
} from "../../../abstract/conversation-agent.interface.js";

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
function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
export class TestChatAgentAdapter extends ConversationAgent {
  http;
  endpoint;
  cancelled = new Set();
  constructor({ http, endpoint = "/api/test" }) {
    super();
    if (!http) throw new Error("TestChatAgentAdapter requires an HttpClient");
    this.http = http;
    this.endpoint = endpoint;
  }
  async *submit(turn, generationId) {
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
      const kind = REPLY_KINDS[row.type];
      const event = agentEvent(kind, row.text, generationId, {
        detail: { replyType: row.type },
      });
      if (event) yield event;
    }
    const terminal = agentEvent(AgentEventKind.TERMINAL, "", generationId);
    if (terminal) yield terminal;
  }
  cancel(generationId) {
    this.cancelled.add(generationId);
  }
}
