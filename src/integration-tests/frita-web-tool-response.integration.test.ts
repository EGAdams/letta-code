/**
 * Integration test: Frita web-tool response.
 * Mirrors scissari-web-tool-response: verifies Frita can call web_fetch_exa
 * (Exa MCP tool) and return a user-visible answer without stall errors.
 *
 * To run: LETTA_RUN_FRITA_TEST=1 bun test frita-web-tool-response
 */

import { beforeEach, describe, expect } from "bun:test";
import { getClient } from "../agent/client";
import { AgentTestContext } from "./framework/AgentTestContext";
import { FritaAgent } from "./framework/agents/FritaAgent";
import { resetAllLoggers } from "./logger-helpers";

const ctx = new AgentTestContext(FritaAgent);
const LOGGER_ID = "FritaWebToolResponse_2026";

const TEST_URL =
  "https://americansjewelry.com/americanjewelry_live_upload_guide.html";

const STALL_FRAGMENTS = [
  "message path to the other agent likely stalled",
  "I ran into an issue completing that request",
  "response was lost during a tool workflow",
];

function isStallError(text: string): boolean {
  const lower = text.toLowerCase();
  return STALL_FRAGMENTS.some((s) => lower.includes(s.toLowerCase()));
}

describe("Frita web tool response", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  ctx.maybeTest(
    "web_fetch_exa call via letta-code produces a user-visible response, not a stall error",
    async () => {
      await ctx.initSettings();
      const logger = await ctx.createLogger(
        LOGGER_ID,
        "frita-web-tool-response",
      );
      await logger.clearLogs("FritaWebToolResponse test started.");

      const prompt = `Fetch this URL and tell me the first section heading: ${TEST_URL}`;
      await logger.log(`Prompt: ${prompt}`);

      const runner = ctx.createStreamRunner({
        new: true,
        yolo: true,
        timeoutMs: 90_000,
      });
      const result = await runner.run(prompt);

      const events = ctx.parser.parseLines(result.stdout);
      const resultText = ctx.parser.extractResultText(events);
      const messageText = ctx.parser.extractMessageText(events);
      const responseText = resultText || messageText;

      await logger.log(
        `exit=${result.exitCode} events=${events.length} resultLen=${resultText.length} msgLen=${messageText.length}`,
      );
      await logger.log(`Result preview: ${responseText.slice(0, 200)}`);

      expect(result.exitCode).toBe(0);
      expect(responseText.trim().length).toBeGreaterThan(0);

      if (isStallError(responseText)) {
        await logger.log(
          `ERROR: response is a stall error: ${responseText.slice(0, 200)}`,
        );
      }
      expect(isStallError(responseText)).toBe(false);
      await logger.log(
        `PASS: Frita returned user-visible text (${responseText.length} chars) without stall error`,
      );
      await logger.flush();
    },
    { timeout: 120_000 },
  );

  ctx.maybeTest(
    "Exa MCP tool is registered and attached to Frita",
    async () => {
      await ctx.initSettings();
      const logger = await ctx.createLogger(LOGGER_ID, "frita-exa-health");

      const client = await getClient();

      try {
        const toolsPage = await client.tools.list({
          name: "web_fetch_exa",
          limit: 5,
        });
        const tool = toolsPage.items.find((t) => t.name === "web_fetch_exa");
        expect(tool).toBeDefined();
        expect(tool?.tool_type).toBe("external_mcp");
        await logger.log(
          `web_fetch_exa found: id=${tool?.id} type=${tool?.tool_type}`,
        );

        const agentToolsPage = await client.agents.tools.list(
          FritaAgent.agentId,
          { limit: 50 },
        );
        const attached = agentToolsPage.getPaginatedItems().map((t) => t.name);
        expect(attached).toContain("web_fetch_exa");
        await logger.log("web_fetch_exa attached to Frita");

        await logger.log("PASS: Exa MCP tool registered and attached to Frita");
      } catch (err) {
        await logger.log(
          `ERROR: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        await logger.flush();
      }
    },
    { timeout: 30_000 },
  );
});
