import type { IAgentUnderTest } from "../IAgentUnderTest";

export const ScissariAgent: IAgentUnderTest = {
  agentId: "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa",
  baseUrl: "http://100.80.49.10:8283",
  apiKey: "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8",
  displayName: "Scissari",
  enableFlag: "LETTA_RUN_SCISSARI_TEST",
  requiredTools: [
    "web_fetch_exa",
    "web_search_exa",
    "executor_run",
    "send_message_to_agent_and_wait_for_reply",
    "send_message_to_agent_async",
  ],
  legacyTools: ["web_search", "fetch_webpage"],
};
