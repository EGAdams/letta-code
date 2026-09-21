import {
  type AgentEvent,
  ConversationAgent,
  type ConversationTurn,
} from "../../../abstract/conversation-agent.interface.js";
interface StoragePort {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}
export interface StreamingLettaAgentDependencies {
  fetchFn?: typeof fetch;
  storage?: StoragePort | null;
  endpoint?: string;
}
/** Adapter from streamed NDJSON provider records to the conversation port. */
export declare class StreamingLettaAgentAdapter extends ConversationAgent {
  private readonly fetchFn;
  private readonly storage;
  private readonly endpoint;
  private readonly controllers;
  constructor({ fetchFn, storage, endpoint }?: StreamingLettaAgentDependencies);
  submit(
    turn: ConversationTurn,
    generationId: string,
  ): AsyncGenerator<AgentEvent, void, unknown>;
  cancel(generationId: string): void;
  private key;
  private readConversationId;
  private rememberConversationId;
}
