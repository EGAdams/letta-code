import type {
  AgentState,
  AgentUpdateParams,
} from "@letta-ai/letta-client/resources/agents/agents";
import { DEFAULT_SUMMARIZATION_MODEL } from "../constants";

type AgentStateReconcileClient = {
  agents: {
    update: (agentID: string, body: AgentUpdateParams) => Promise<AgentState>;
  };
};

export interface ReconcileAgentStateResult {
  updated: boolean;
  agent: AgentState;
  appliedTweaks: string[];
  skippedTweaks: string[];
}

export async function reconcileExistingAgentState(
  client: AgentStateReconcileClient,
  agent: AgentState,
): Promise<ReconcileAgentStateResult> {
  const patch: AgentUpdateParams = {};
  const appliedTweaks: string[] = [];
  const skippedTweaks: string[] = [];

  const configuredCompactionModel =
    typeof agent.compaction_settings?.model === "string"
      ? agent.compaction_settings.model.trim()
      : "";

  if (!configuredCompactionModel) {
    patch.compaction_settings = {
      ...(agent.compaction_settings ?? {}),
      model: DEFAULT_SUMMARIZATION_MODEL,
    };
    appliedTweaks.push("set_compaction_model");
  }

  if (appliedTweaks.length === 0) {
    return {
      updated: false,
      agent,
      appliedTweaks,
      skippedTweaks,
    };
  }

  const updatedAgent = await client.agents.update(agent.id, patch);
  return {
    updated: true,
    agent: updatedAgent,
    appliedTweaks,
    skippedTweaks,
  };
}
