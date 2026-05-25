import type { LettaStreamingResponse } from "@letta-ai/letta-client/resources/agents/messages";
import type { DrainStreamHook } from "../cli/helpers/stream";

// One accordion section in the localhost:8080 viewer.
export interface IAgentEventLogger {
  init(): Promise<void>;
  log(message: string): Promise<void>;
  clear(label?: string): Promise<void>;
}

// Routes each stream chunk to the correct accordion.
export interface IAgentLoggerFactory {
  getLogger(chunk: LettaStreamingResponse): IAgentEventLogger | null;
  initAll(): Promise<void>;
  clearAll(): Promise<void>;
}

// Plugs into drainStream via the onChunkProcessed hook.
// The drainHook must never block — logging is fire-and-forget inside it.
export interface IAgentSessionLogger {
  readonly drainHook: DrainStreamHook;
  onSessionStart(agentId: string): Promise<void>;
  onSessionEnd(): Promise<void>;
}
