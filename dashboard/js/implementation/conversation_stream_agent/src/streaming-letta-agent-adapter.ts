import {
  type AgentEvent,
  AgentEventKind,
  agentEvent,
  ConversationAgent,
  type ConversationTurn,
  TurnCancelledError,
} from "../../../abstract/conversation-agent.interface.js";

interface StoragePort {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

interface StreamEnvelope {
  type: "event" | "error";
  event?: Record<string, unknown> | null;
  error?: string | null;
}

export interface StreamingLettaAgentDependencies {
  fetchFn?: typeof fetch;
  storage?: StoragePort | null;
  endpoint?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function textFromContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((part) => {
      if (typeof part === "string") return part;
      if (!isRecord(part)) return "";
      return typeof part.text === "string" ? part.text : "";
    })
    .join("");
}

function assistantDelta(raw: Record<string, unknown>): string {
  const provider =
    raw.type === "stream_event" && isRecord(raw.event) ? raw.event : raw;
  if (provider.message_type !== "assistant_message") return "";
  return textFromContent(provider.content);
}

/** Adapter from streamed NDJSON provider records to the conversation port. */
export class StreamingLettaAgentAdapter extends ConversationAgent {
  private readonly fetchFn: typeof fetch;
  private readonly storage: StoragePort | null;
  private readonly endpoint: string;
  private readonly controllers = new Map<string, AbortController>();

  constructor({
    fetchFn = globalThis.fetch?.bind(globalThis),
    storage = null,
    endpoint = "/api/letta-code-stream",
  }: StreamingLettaAgentDependencies = {}) {
    super();
    if (typeof fetchFn !== "function")
      throw new Error("StreamingLettaAgentAdapter requires fetch");
    this.fetchFn = fetchFn;
    this.storage = storage;
    this.endpoint = endpoint;
  }

  override async *submit(
    turn: ConversationTurn,
    generationId: string,
  ): AsyncGenerator<AgentEvent, void, unknown> {
    if (!turn?.agent || typeof turn.text !== "string" || !turn.text.trim())
      throw new Error("StreamingLettaAgentAdapter requires an agent and text");
    const controller = new AbortController();
    this.controllers.set(generationId, controller);
    const conversationId =
      turn.conversationId ?? this.readConversationId(turn.agent);
    try {
      const response = await this.fetchFn(this.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent: turn.agent,
          text: turn.text,
          conversation_id: conversationId,
        }),
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        let detail = "";
        try {
          const body = await response.json();
          detail = typeof body?.error === "string" ? body.error : "";
        } catch {}
        throw new Error(
          `HTTP ${response.status}${detail ? ` — ${detail}` : ""}`,
        );
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let terminal = false;
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const lines = buffer.split("\n");
        buffer = done ? "" : (lines.pop() ?? "");
        for (const line of lines) {
          if (!line.trim()) continue;
          let envelope: StreamEnvelope;
          try {
            envelope = JSON.parse(line) as StreamEnvelope;
          } catch {
            throw new Error("Toyota stream returned malformed JSON");
          }
          if (!isRecord(envelope)) continue;
          if (envelope.type === "error")
            throw new Error(envelope.error || "Toyota stream failed");
          const raw = envelope.event;
          if (!isRecord(raw)) continue;
          if (raw.type === "error")
            throw new Error(
              typeof raw.message === "string"
                ? raw.message
                : "Toyota stream failed",
            );
          if (raw.type === "result") {
            const nextConversationId =
              typeof raw.conversation_id === "string"
                ? raw.conversation_id
                : null;
            this.rememberConversationId(turn.agent, nextConversationId);
            terminal = true;
            const event = agentEvent(
              AgentEventKind.TERMINAL,
              "",
              generationId,
              {
                detail: { conversationId: nextConversationId },
              },
            );
            if (event) yield event;
            continue;
          }
          const delta = assistantDelta(raw);
          if (!delta) continue;
          const event = agentEvent(
            AgentEventKind.ASSISTANT_TEXT,
            delta,
            generationId,
          );
          if (event) yield event;
        }
        if (done) break;
      }
      if (!terminal) throw new Error("Toyota stream ended without a result");
    } catch (cause) {
      if (controller.signal.aborted) throw new TurnCancelledError(generationId);
      throw cause;
    } finally {
      this.controllers.delete(generationId);
    }
  }

  override cancel(generationId: string): void {
    this.controllers.get(generationId)?.abort();
  }

  private key(agent: string): string {
    return `msi-conv-${agent}`;
  }

  private readConversationId(agent: string): string | null {
    return this.storage?.getItem(this.key(agent)) || null;
  }

  private rememberConversationId(
    agent: string,
    conversationId: string | null,
  ): void {
    if (conversationId) this.storage?.setItem(this.key(agent), conversationId);
  }
}
