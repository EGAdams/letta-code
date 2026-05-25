import { beforeAll, describe, expect, mock, test } from "bun:test";
import type {
  AgentState,
  AgentUpdateParams,
} from "@letta-ai/letta-client/resources/agents/agents";
import type { Tool } from "@letta-ai/letta-client/resources/tools";
import {
  DEFAULT_ATTACHED_BASE_TOOLS,
  reconcileExistingAgentState,
} from "../../agent/reconcileExistingAgentState";
import { settingsManager } from "../../settings-manager";

function mkTool(id: string, name: string): Tool {
  return { id, name } as Tool;
}

function mkAgentState(overrides: Partial<AgentState>): AgentState {
  return {
    id: "agent-test",
    tools: [],
    name: "test-agent",
    system: "system",
    agent_type: "letta_v1_agent",
    blocks: [],
    llm_config: {} as AgentState["llm_config"],
    memory: { blocks: [] } as AgentState["memory"],
    sources: [],
    tags: [],
    ...overrides,
  } as AgentState;
}

describe("reconcileExistingAgentState", () => {
  beforeAll(async () => {
    await settingsManager.initialize();
  });

  test("does not update when compaction model and attached tools are already correct", async () => {
    const agent = mkAgentState({
      tools: [
        mkTool("tool-web", "web_search"),
        mkTool("tool-fetch", "fetch_webpage"),
        mkTool("tool-send", "send_message"),
      ],
      compaction_settings: {
        model: "letta/auto",
      },
    });

    const update = mock(() => Promise.resolve(agent));

    const result = await reconcileExistingAgentState(
      {
        agents: { update },
      } as unknown as Parameters<typeof reconcileExistingAgentState>[0],
      agent,
    );

    expect(result.updated).toBe(false);
    expect(result.appliedTweaks).toEqual([]);
    expect(update).not.toHaveBeenCalled();
  });

  test("updates missing compaction model without rewriting attached tools", async () => {
    const initialAgent = mkAgentState({
      tools: [
        mkTool("tool-web", "web_search"),
        mkTool("tool-convo", "conversation_search"),
      ],
      compaction_settings: {
        mode: "sliding_window",
        model: "",
      },
    });

    const updatedAgent = mkAgentState({
      tools: [
        mkTool("tool-web", "web_search"),
        mkTool("tool-fetch", "fetch_webpage"),
        mkTool("tool-send", "send_message"),
        mkTool("tool-convo", "conversation_search"),
      ],
      compaction_settings: {
        mode: "sliding_window",
        model: "letta/auto",
      },
    });

    const update = mock((_agentID: string, _body: AgentUpdateParams) =>
      Promise.resolve(updatedAgent),
    );
    const list = mock((query?: { name?: string | null }) => {
      if (query?.name === "fetch_webpage") {
        return Promise.resolve({
          items: [mkTool("tool-fetch", "fetch_webpage")],
        });
      }
      if (query?.name === "send_message") {
        return Promise.resolve({
          items: [mkTool("tool-send", "send_message")],
        });
      }
      return Promise.resolve({ items: [] as Tool[] });
    });

    const result = await reconcileExistingAgentState(
      {
        agents: { update },
      } as unknown as Parameters<typeof reconcileExistingAgentState>[0],
      initialAgent,
    );

    expect(result.updated).toBe(true);
    expect(result.appliedTweaks).toEqual(["set_compaction_model"]);
    expect(result.agent).toBe(updatedAgent);
    expect(list).toHaveBeenCalledTimes(2);
    expect(list).toHaveBeenCalledWith({ name: "fetch_webpage", limit: 10 });
    expect(list).toHaveBeenCalledWith({ name: "send_message", limit: 10 });
    expect(update).toHaveBeenCalledTimes(1);
    expect(update).toHaveBeenCalledWith("agent-test", {
      compaction_settings: {
        mode: "sliding_window",
        model: "letta/letta-free",
      },
      tool_ids: ["tool-web", "tool-fetch", "tool-send"],
    });

    expect(DEFAULT_ATTACHED_BASE_TOOLS).toEqual([
      "web_search",
      "fetch_webpage",
      "send_message",
    ]);
  });
});
