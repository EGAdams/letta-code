import { beforeEach, describe, expect, test } from "bun:test";
import { getClient } from "../agent/client";
import { reconcileExistingAgentState } from "../agent/reconcileExistingAgentState";
import { RemoteLogger } from "../logger/RemoteLogger";
import { settingsManager } from "../settings-manager";
import { resetAllLoggers } from "./logger-helpers";

const SCISSARI_AGENT_ID = "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa";
const DEFAULT_BASE_URL = "http://100.80.49.10:8283";
const TEST_API_KEY = "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8";
const LOGGER_ID = "ScissariToolParity_2026";
const REQUIRED_TOOLS = [
  "web_fetch_exa",
  "web_search_exa",
  "executor_run",
  "send_message_to_agent_and_wait_for_reply",
  "send_message_to_agent_async",
];

function sortNames(names: Iterable<string>): string[] {
  return [...names].sort();
}

function formatNames(names: Iterable<string>): string {
  return sortNames(names).join(", ");
}

async function listAgentToolNames(agentId: string): Promise<string[]> {
  const client = await getClient();
  const toolsPage = await client.agents.tools.list(agentId, { limit: 50 });
  return sortNames(
    toolsPage
      .getPaginatedItems()
      .map((tool) => tool.name)
      .filter((name): name is string => typeof name === "string"),
  );
}

async function resolveToolIdByName(name: string): Promise<string> {
  const client = await getClient();
  const toolsPage = await client.tools.list({ name, limit: 10 });
  const tool = toolsPage.items.find((item) => item.name === name);
  if (!tool?.id) {
    throw new Error(`Required server tool not found: ${name}`);
  }
  return tool.id;
}

async function ensureExactToolSet(
  agentId: string,
  requiredNames: readonly string[],
): Promise<void> {
  const client = await getClient();
  const toolsPage = await client.agents.tools.list(agentId, { limit: 50 });
  const attachedTools = toolsPage.getPaginatedItems();
  const attachedByName = new Map(
    attachedTools
      .filter(
        (tool): tool is typeof tool & { id: string; name: string } =>
          typeof tool.id === "string" && typeof tool.name === "string",
      )
      .map((tool) => [tool.name, tool.id]),
  );

  for (const name of requiredNames) {
    if (attachedByName.has(name)) {
      continue;
    }
    const toolId = await resolveToolIdByName(name);
    await client.agents.tools.attach(toolId, { agent_id: agentId });
  }

  for (const [name, toolId] of attachedByName) {
    if (!requiredNames.includes(name)) {
      await client.agents.tools.detach(toolId, { agent_id: agentId });
    }
  }
}

describe("Scissari tool parity integration", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" ? test : test.skip;

  maybeTest(
    "reconciling Scissari does not rewrite attached tools to legacy defaults",
    async () => {
      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs("Scissari tool parity test run started.");
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[scissari-tool-parity] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }

      const log = async (message: string) => {
        console.log(`[scissari-tool-parity] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch (err) {
          console.warn(
            `[scissari-tool-parity] log failed: ${err instanceof Error ? err.message : String(err)}`,
          );
        }
      };

      const expectedNames = sortNames(REQUIRED_TOOLS);

      try {
        await log(
          "Repairing Scissari to the expected five-tool set before reconcile",
        );
        await ensureExactToolSet(SCISSARI_AGENT_ID, REQUIRED_TOOLS);

        const beforeNames = await listAgentToolNames(SCISSARI_AGENT_ID);
        await log(`Before reconcile: ${formatNames(beforeNames)}`);
        expect(beforeNames).toEqual(expectedNames);

        const client = await getClient();
        const agent = await client.agents.retrieve(SCISSARI_AGENT_ID, {
          include: ["agent.tools"],
        });

        const reconcileResult = await reconcileExistingAgentState(
          client,
          agent,
        );
        await log(
          `Reconcile updated=${reconcileResult.updated} appliedTweaks=${reconcileResult.appliedTweaks.join(",") || "(none)"}`,
        );

        const afterNames = await listAgentToolNames(SCISSARI_AGENT_ID);
        await log(`After reconcile: ${formatNames(afterNames)}`);

        if (afterNames.join("|") !== expectedNames.join("|")) {
          throw new Error(
            `Scissari tool set changed across reconcile. ` +
              `Expected: ${formatNames(expectedNames)}. ` +
              `Before: ${formatNames(beforeNames)}. ` +
              `After: ${formatNames(afterNames)}.`,
          );
        }

        expect(afterNames).toEqual(expectedNames);
        await log("PASS: reconcile preserved Scissari's exact tool set");
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      } finally {
        await ensureExactToolSet(SCISSARI_AGENT_ID, REQUIRED_TOOLS);
        const repairedNames = await listAgentToolNames(SCISSARI_AGENT_ID);
        await log(`Final repaired state: ${formatNames(repairedNames)}`);
        if (loggerReady) await logger.flushLogs();
      }
    },
    { timeout: 120000 },
  );
});
