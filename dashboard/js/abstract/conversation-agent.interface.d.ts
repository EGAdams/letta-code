export interface ConversationTurn {
  agent: string;
  text: string;
  conversationId?: string | null;
}

export interface AgentEvent {
  kind: string;
  text: string;
  generationId: string;
  name?: string;
  detail?: Record<string, unknown> | null;
}

export const AgentEventKind: Readonly<{
  ASSISTANT_TEXT: "assistant_text";
  REASONING: "reasoning";
  TOOL_CALL: "tool_call";
  TOOL_RESULT: "tool_result";
  STATUS: "status";
  TERMINAL: "terminal";
}>;

export function agentEvent(
  kind: string,
  text: string,
  generationId: string,
  extra?: { name?: string; detail?: Record<string, unknown> | null },
): AgentEvent | null;

export class TurnCancelledError extends Error {
  readonly generationId: string;
  constructor(generationId: string);
}

export class ConversationAgent {
  submit(
    turn: ConversationTurn,
    generationId: string,
  ): AsyncGenerator<AgentEvent, void, unknown>;
  cancel(generationId: string): void;
}
