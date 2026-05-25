import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { getClient } from "../agent/client";
import { RemoteLogger } from "../logger/RemoteLogger";
import { settingsManager } from "../settings-manager";
import { resetLogger } from "./logger-helpers";

const DEFAULT_BASE_URL = "http://100.80.49.10:8283";
const TEST_API_KEY = "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8";

const LOGGER_ID = "ToolAttach_Lifecycle_2026";

// Minimal Python source for a test tool the Letta server will accept.
const TEST_TOOL_SOURCE = `
def test_greet(name: str) -> str:
    """
    Returns a greeting for the given name.

    Args:
        name: The name to greet.

    Returns:
        A greeting string.
    """
    return f"Hello, {name}!"
`.trim();

function makeLoggerHelpers(logger: RemoteLogger, prefix: string) {
  let loggerReady = false;

  const init = async () => {
    try {
      await logger.init();
      loggerReady = true;
    } catch (err) {
      console.warn(
        `[${prefix}] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
  };

  const log = async (message: string) => {
    console.log(`[${prefix}] ${message}`);
    if (loggerReady) {
      try {
        await logger.log(message);
      } catch (err) {
        console.error(
          `[${prefix}] log failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
    }
  };

  const flushLogs = async () => {
    if (loggerReady) {
      try {
        await logger.flushLogs();
      } catch (err) {
        console.error(
          `[${prefix}] flushLogs failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
    }
  };

  return { init, log, flushLogs };
}

describe("Tool attach lifecycle integration", () => {
  const maybeTest =
    process.env.LETTA_RUN_TOOL_ATTACH_TEST === "1" ? test : test.skip;

  let createdAgentId: string | null = null;
  let createdToolId: string | null = null;

  beforeAll(async () => {
    process.env.LETTA_BASE_URL = process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
    process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
    await settingsManager.initialize();
    await resetLogger(LOGGER_ID);
  });

  afterAll(async () => {
    // Best-effort cleanup so test runs don't leave orphaned resources.
    const client = await getClient();
    if (createdToolId) {
      try {
        await client.tools.delete(createdToolId);
        console.log(`[ToolAttach:cleanup] deleted tool ${createdToolId}`);
      } catch (err) {
        console.warn(
          `[ToolAttach:cleanup] failed to delete tool ${createdToolId}: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
    }
    if (createdAgentId) {
      try {
        await client.agents.delete(createdAgentId);
        console.log(`[ToolAttach:cleanup] deleted agent ${createdAgentId}`);
      } catch (err) {
        console.warn(
          `[ToolAttach:cleanup] failed to delete agent ${createdAgentId}: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
    }
  });

  maybeTest(
    "creates a tool, attaches it to a new agent, verifies, then detaches",
    async () => {
      const logger = new RemoteLogger(LOGGER_ID);
      const { init, log, flushLogs } = makeLoggerHelpers(logger, "ToolAttach");
      await init();

      const client = await getClient();

      // ── Phase 1: create a tool ────────────────────────────────────────────
      await log("Phase 1: creating tool via client.tools.create");
      const tool = await client.tools.create({
        source_code: TEST_TOOL_SOURCE,
        source_type: "python",
        description: "Integration test tool — safe to delete",
        tags: ["integration-test"],
      });
      createdToolId = tool.id;
      await log(`tool created: id=${tool.id} name=${tool.name ?? "(none)"}`);
      expect(tool.id).toMatch(/^tool-/);

      // ── Phase 2: create an agent ──────────────────────────────────────────
      await log("Phase 2: creating agent via client.agents.create");
      // biome-ignore lint/suspicious/noImplicitAnyLet: assigned in try/catch below
      let agent;
      try {
        agent = await client.agents.create({
          name: `tool-attach-integration-test-${Date.now()}`,
          llm_config: {
            model_endpoint_type: "chatgpt_oauth",
            model: "gpt-5.3-codex",
            context_window: 140000,
            parallel_tool_calls: true,
            reasoning_effort: "medium",
            enable_reasoner: true,
          },
          include_base_tools: false,
          include_base_tool_rules: false,
        });
      } catch (err) {
        const detail = err instanceof Error ? err.message : JSON.stringify(err);
        await log(`ERROR: agent create failed — ${detail}`);
        throw err;
      }
      createdAgentId = agent.id;
      await log(`agent created: id=${agent.id}`);
      expect(agent.id).toMatch(/^agent-/);

      // ── Phase 3: attach the tool ──────────────────────────────────────────
      await log(
        `Phase 3: attaching tool ${createdToolId} to agent ${createdAgentId}`,
      );
      let attachedAgent: Awaited<
        ReturnType<typeof client.agents.tools.attach>
      > | null = null;
      try {
        attachedAgent = await client.agents.tools.attach(createdToolId, {
          agent_id: createdAgentId,
        });
      } catch (err) {
        const detail = err instanceof Error ? err.message : JSON.stringify(err);
        await log(
          `ERROR: attach failed — ${detail}. ` +
            "Likely causes: tool ID not found (was it created in a different org?), " +
            "agent ID not found, or DB constraint (tool already attached).",
        );
        throw err;
      }
      await log("attach succeeded");

      // ── Phase 4: verify the tool appears in the agent's tool list ─────────
      await log("Phase 4: verifying tool appears in agent tool list");
      const toolsPage = await client.agents.tools.list(createdAgentId);
      const toolItems = toolsPage.getPaginatedItems();
      const found = toolItems.some((t) => t.id === createdToolId);
      if (!found) {
        await log(
          `ERROR: tool ${createdToolId} not in agent tool list after attach. ` +
            `attached agent tools: ${toolItems.map((t) => t.id).join(", ")}`,
        );
      }
      expect(found).toBe(true);
      await log("tool is present in agent tool list: PASS");

      // Also validate the returned agent state from attach (may be null on 0.16.x)
      if (attachedAgent !== null) {
        const attachedTools = attachedAgent.tools ?? [];
        const foundInReturn = attachedTools.some((t) => t.id === createdToolId);
        await log(
          `attach return: tool present=${foundInReturn} (${attachedTools.length} total tools)`,
        );
      }

      // ── Phase 5: detach the tool ──────────────────────────────────────────
      await log(
        `Phase 5: detaching tool ${createdToolId} from agent ${createdAgentId}`,
      );
      try {
        await client.agents.tools.detach(createdToolId, {
          agent_id: createdAgentId,
        });
      } catch (err) {
        const detail = err instanceof Error ? err.message : JSON.stringify(err);
        await log(`WARN: detach failed (non-fatal for test): ${detail}`);
      }

      const afterDetach = await client.agents.tools.list(createdAgentId);
      const afterItems = afterDetach.getPaginatedItems();
      const stillPresent = afterItems.some((t) => t.id === createdToolId);
      expect(stillPresent).toBe(false);
      await log(
        "tool absent from agent tool list after detach: PASS — test complete",
      );
      await flushLogs();
    },
    { timeout: 60000 },
  );

  maybeTest(
    "attach with nonexistent tool ID returns a meaningful error (not silent 500)",
    async () => {
      const logger = new RemoteLogger(LOGGER_ID);
      const { init, log, flushLogs } = makeLoggerHelpers(
        logger,
        "ToolAttach:BadId",
      );
      await init();

      const client = await getClient();

      // We need a real agent to attempt the attach against.
      await log("creating throwaway agent for bad-tool-id test");
      // biome-ignore lint/suspicious/noImplicitAnyLet: assigned in try/catch below
      let agent;
      try {
        agent = await client.agents.create({
          name: `tool-attach-badid-test-${Date.now()}`,
          llm_config: {
            model_endpoint_type: "chatgpt_oauth",
            model: "gpt-5.3-codex",
            context_window: 140000,
            parallel_tool_calls: true,
            reasoning_effort: "medium",
            enable_reasoner: true,
          },
          include_base_tools: false,
          include_base_tool_rules: false,
        });
      } catch (err) {
        const detail = err instanceof Error ? err.message : JSON.stringify(err);
        await log(`ERROR: agent create failed — ${detail}`);
        throw err;
      }
      const agentId = agent.id;
      await log(`agent created: id=${agentId}`);

      const fakeToolId = "tool-00000000-0000-0000-0000-000000000000";
      await log(`attaching nonexistent tool ${fakeToolId} to agent ${agentId}`);

      let caughtStatus: number | null = null;
      try {
        await client.agents.tools.attach(fakeToolId, { agent_id: agentId });
        await log("ERROR: expected attach to throw but it succeeded");
        // If somehow it doesn't throw, clean up and fail explicitly.
        await client.agents.delete(agentId).catch(() => {});
        throw new Error("Expected attach to fail for nonexistent tool ID");
      } catch (err) {
        const status =
          err != null && typeof err === "object" && "status" in err
            ? (err as { status: number }).status
            : null;
        caughtStatus = status;
        const detail = err instanceof Error ? err.message : JSON.stringify(err);
        await log(
          `attach threw as expected: status=${status ?? "unknown"} detail=${detail.slice(0, 200)}`,
        );
      } finally {
        await client.agents.delete(agentId).catch((e: unknown) => {
          console.warn(
            `[ToolAttach:BadId] cleanup delete failed: ${e instanceof Error ? e.message : String(e)}`,
          );
        });
      }

      // The server SHOULD return 4xx (404/422) not a 500 database error.
      // If you see 500 here it means the server is leaking DB errors to the client —
      // that is the bug this test surfaces.
      expect(caughtStatus).not.toBe(500);
      expect(caughtStatus !== null && [404, 422].includes(caughtStatus)).toBe(
        true,
      );
      await log(
        `nonexistent tool attach returned ${caughtStatus} (not 500): PASS — test complete`,
      );
      await flushLogs();
    },
    { timeout: 30000 },
  );
});
