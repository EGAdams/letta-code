import type { IAgentSessionLogger } from "./agent-event-logger";
import {
  SCISSARI_AGENT_ID,
  ScissariSessionLogger,
} from "./scissari-session-logger";

// Returns a session logger for known agents, null for all others.
// Extend this switch when adding loggers for additional agents.
export function createAgentSessionLogger(
  agentId: string,
): IAgentSessionLogger | null {
  if (agentId === SCISSARI_AGENT_ID) {
    return new ScissariSessionLogger();
  }
  return null;
}
