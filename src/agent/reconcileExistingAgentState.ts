import type {
  AgentState,
  AgentUpdateParams,
} from "@letta-ai/letta-client/resources/agents/agents";
import type { Model } from "@letta-ai/letta-client/resources/models/models";
import type { Tool } from "@letta-ai/letta-client/resources/tools";
import { DEFAULT_SUMMARIZATION_MODEL } from "../constants";
import { resolveDefaultAgentModel } from "./serverModelSelection";

export const DEFAULT_ATTACHED_BASE_TOOLS = [
  "web_search",
  "fetch_webpage",
  "send_message",
] as const;

type AgentStateReconcileClient = {
  agents: {
    update: (agentID: string, body: AgentUpdateParams) => Promise<AgentState>;
  };
  models?: {
    list: () => Promise<Model[]>;
  };
  tools: {
    list: (query?: { name?: string | null; limit?: number | null }) => Promise<{
      items: Tool[];
    }>;
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
    const defaultCompactionModel =
      (await resolveDefaultAgentModel({
        client,
        preferredModel: DEFAULT_SUMMARIZATION_MODEL,
        fallbackModel: agent.model?.trim() || undefined,
      })) || DEFAULT_SUMMARIZATION_MODEL;
    patch.compaction_settings = {
      ...(agent.compaction_settings ?? {}),
      model: defaultCompactionModel,
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
