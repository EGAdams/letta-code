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

const LEGACY_TOOLS = ["web_search", "fetch_webpage"];

describe("Scissari tool parity integration", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" ? test : test.skip;

  // Detects the bug where Scissari silently loses her tools and falls back to
  // legacy defaults. This has happened at least once (discovered 2026-05-27)
  // and left her with only web_search + fetch_webpage for days.
  maybeTest(
    "Scissari has all required tools and no legacy defaults",
    async () => {
      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch {
        /* non-fatal */
      }

      const log = async (message: string) => {
        console.log(`[scissari-tool-check] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(message);
          } catch {
            /* non-fatal */
          }
        }
      };

      try {
        const toolNames = await listAgentToolNames(SCISSARI_AGENT_ID);
        await log(`Current tools: ${formatNames(toolNames)}`);

        // Fail loudly if any required tool is missing
        const missing = REQUIRED_TOOLS.filter((t) => !toolNames.includes(t));
        if (missing.length > 0) {
          throw new Error(
            `Scissari is missing required tools: ${missing.join(", ")}. ` +
              `Full list: ${formatNames(toolNames)}. ` +
              `Run the repair: PATCH /v1/agents/${SCISSARI_AGENT_ID}/tools/attach/{toolId}`,
          );
        }

        // Fail loudly if legacy defaults crept back in
        const legacy = LEGACY_TOOLS.filter((t) => toolNames.includes(t));
        if (legacy.length > 0) {
          throw new Error(
            `Scissari has legacy default tools that should not be present: ${legacy.join(", ")}. ` +
              `These indicate her tool set was reset to new-agent defaults.`,
          );
        }

        expect(toolNames).toEqual(sortNames(REQUIRED_TOOLS));
        await log(
          `PASS: Scissari has correct tool set: ${formatNames(toolNames)}`,
        );
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      } finally {
        if (loggerReady) await logger.flushLogs();
      }
    },
    { timeout: 60000 },
  );

  // Verifies that a system-prompt PATCH (the most common startup write) does
  // not inadvertently reset Scissari's tool_ids on the Letta server.
  maybeTest(
    "PATCH system prompt does not strip Scissari's tools",
    async () => {
      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch {
        /* non-fatal */
      }

      const log = async (message: string) => {
        console.log(`[scissari-patch-test] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(message);
          } catch {
            /* non-fatal */
          }
        }
      };

      const client = await getClient();

      // Ensure known-good state before test
      await ensureExactToolSet(SCISSARI_AGENT_ID, REQUIRED_TOOLS);
      const before = await listAgentToolNames(SCISSARI_AGENT_ID);
      await log(`Before PATCH: ${formatNames(before)}`);

      try {
        // Simulate a no-op system prompt PATCH (same as letta-code does on startup)
        const agent = await client.agents.retrieve(SCISSARI_AGENT_ID);
        const currentSystem = agent.system ?? "";
        await client.agents.update(SCISSARI_AGENT_ID, {
          system: currentSystem,
        });

        const after = await listAgentToolNames(SCISSARI_AGENT_ID);
        await log(`After PATCH: ${formatNames(after)}`);

        if (after.join("|") !== before.join("|")) {
          throw new Error(
            `System-prompt PATCH changed Scissari's tool set. ` +
              `Before: ${formatNames(before)}. After: ${formatNames(after)}.`,
          );
        }

        expect(after).toEqual(before);
        await log("PASS: system prompt PATCH preserved tool set");
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      } finally {
        // Always restore to required tool set
        await ensureExactToolSet(SCISSARI_AGENT_ID, REQUIRED_TOOLS);
        if (loggerReady) await logger.flushLogs();
      }
    },
    { timeout: 60000 },
  );

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
        await log(
          `PASS: test complete — tool set: ${formatNames(repairedNames)}`,
        );
        if (loggerReady) await logger.flushLogs();
      }
    },
    { timeout: 120000 },
  );
});
