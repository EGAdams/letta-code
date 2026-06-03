import { beforeEach, describe, expect } from "bun:test";
import { getClient } from "../agent/client";
import { reconcileExistingAgentState } from "../agent/reconcileExistingAgentState";
import { AgentTestContext } from "./framework/AgentTestContext";
import { FritaAgent } from "./framework/agents/FritaAgent";
import {
  ensureExactToolSet,
  formatNames,
  listAgentToolNames,
  sortNames,
} from "./framework/utils/lettaToolUtils";
import { resetAllLoggers } from "./logger-helpers";

const ctx = new AgentTestContext(FritaAgent);
const LOGGER_ID = "FritaToolParity_2026";
const REQUIRED_TOOLS = FritaAgent.requiredTools ?? [];
const LEGACY_TOOLS = FritaAgent.legacyTools ?? [];

describe("Frita tool parity integration", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  ctx.maybeTest(
    "Frita has all required tools and no legacy defaults",
    async () => {
      await ctx.initSettings();
      const logger = await ctx.createLogger(LOGGER_ID, "frita-tool-check");

      try {
        const client = await getClient();
        const toolNames = await listAgentToolNames(client, FritaAgent.agentId);
        await logger.log(`Current tools: ${formatNames(toolNames)}`);

        const missing = REQUIRED_TOOLS.filter((t) => !toolNames.includes(t));
        if (missing.length > 0) {
          throw new Error(
            `Frita is missing required tools: ${missing.join(", ")}. Full list: ${formatNames(toolNames)}.`,
          );
        }
        const legacy = LEGACY_TOOLS.filter((t) => toolNames.includes(t));
        if (legacy.length > 0) {
          throw new Error(
            `Frita has legacy default tools that should not be present: ${legacy.join(", ")}.`,
          );
        }
        expect(toolNames).toEqual(sortNames(REQUIRED_TOOLS));
        await logger.log(
          `PASS: Frita has correct tool set: ${formatNames(toolNames)}`,
        );
      } catch (err) {
        await logger.log(
          `ERROR: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        await logger.flush();
      }
    },
    { timeout: 60000 },
  );

  ctx.maybeTest(
    "PATCH system prompt does not strip Frita's tools",
    async () => {
      await ctx.initSettings();
      const logger = await ctx.createLogger(LOGGER_ID, "frita-patch-test");

      const client = await getClient();
      await ensureExactToolSet(client, FritaAgent.agentId, REQUIRED_TOOLS);
      const before = await listAgentToolNames(client, FritaAgent.agentId);
      await logger.log(`Before PATCH: ${formatNames(before)}`);

      try {
        const agent = await client.agents.retrieve(FritaAgent.agentId);
        await client.agents.update(FritaAgent.agentId, {
          system: agent.system ?? "",
        });

        const after = await listAgentToolNames(client, FritaAgent.agentId);
        await logger.log(`After PATCH: ${formatNames(after)}`);

        if (after.join("|") !== before.join("|")) {
          throw new Error(
            `System-prompt PATCH changed Frita's tool set. Before: ${formatNames(before)}. After: ${formatNames(after)}.`,
          );
        }
        expect(after).toEqual(before);
        await logger.log("PASS: system prompt PATCH preserved tool set");
      } catch (err) {
        await logger.log(
          `ERROR: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        await ensureExactToolSet(client, FritaAgent.agentId, REQUIRED_TOOLS);
        await logger.flush();
      }
    },
    { timeout: 60000 },
  );

  ctx.maybeTest(
    "reconciling Frita does not rewrite attached tools to legacy defaults",
    async () => {
      await ctx.initSettings();
      const logger = await ctx.createLogger(LOGGER_ID, "frita-tool-parity");
      await logger.clearLogs("Frita tool parity test run started.");

      const expectedNames = sortNames(REQUIRED_TOOLS);
      const client = await getClient();

      try {
        await logger.log(
          "Repairing Frita to the expected tool set before reconcile",
        );
        await ensureExactToolSet(client, FritaAgent.agentId, REQUIRED_TOOLS);

        const beforeNames = await listAgentToolNames(
          client,
          FritaAgent.agentId,
        );
        await logger.log(`Before reconcile: ${formatNames(beforeNames)}`);
        expect(beforeNames).toEqual(expectedNames);

        const agent = await client.agents.retrieve(FritaAgent.agentId, {
          include: ["agent.tools"],
        });
        const reconcileResult = await reconcileExistingAgentState(
          client,
          agent,
        );
        await logger.log(
          `Reconcile updated=${reconcileResult.updated} appliedTweaks=${reconcileResult.appliedTweaks.join(",") || "(none)"}`,
        );

        const afterNames = await listAgentToolNames(client, FritaAgent.agentId);
        await logger.log(`After reconcile: ${formatNames(afterNames)}`);

        if (afterNames.join("|") !== expectedNames.join("|")) {
          throw new Error(
            `Frita tool set changed across reconcile. Expected: ${formatNames(expectedNames)}. After: ${formatNames(afterNames)}.`,
          );
        }
        expect(afterNames).toEqual(expectedNames);
        await logger.log("PASS: reconcile preserved Frita's exact tool set");
      } catch (err) {
        await logger.log(
          `ERROR: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        await ensureExactToolSet(client, FritaAgent.agentId, REQUIRED_TOOLS);
        const repaired = await listAgentToolNames(client, FritaAgent.agentId);
        await logger.log(
          `PASS: test complete — tool set: ${formatNames(repaired)}`,
        );
        await logger.flush();
      }
    },
    { timeout: 120000 },
  );
});
