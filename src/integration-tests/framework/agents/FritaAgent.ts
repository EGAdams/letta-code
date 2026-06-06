import type { IAgentUnderTest } from "../IAgentUnderTest";

export const FritaAgent: IAgentUnderTest = {
  agentId: "agent-881a883f-edd0-4963-bf67-6ef178b8f018",
  baseUrl: "http://100.80.49.10:8283",
  apiKey: "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8",
  displayName: "Frita",
  enableFlag: "LETTA_RUN_FRITA_TEST",
  requiredTools: [
    "conversation_search",
    "executor_run",
    "memory_insert",
    "memory_replace",
    "relay_message_to_chatgpt",
    "send_message_to_agent_and_wait_for_reply",
    "send_message_to_agent_async",
    "web_fetch_exa",
    "web_search_exa",
  ],
  legacyTools: ["web_search", "fetch_webpage"],
};
