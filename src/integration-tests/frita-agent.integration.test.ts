import { beforeEach, describe, expect } from "bun:test";
import { AgentTestContext } from "./framework/AgentTestContext";
import { FritaAgent } from "./framework/agents/FritaAgent";
import { resetAllLoggers } from "./logger-helpers";

const ctx = new AgentTestContext(FritaAgent);

function extractJsonObject(stdout: string): Record<string, unknown> {
  const start = stdout.indexOf("{");
  if (start < 0) throw new Error(`No JSON object found in stdout:\n${stdout}`);
  return JSON.parse(stdout.slice(start)) as Record<string, unknown>;
}

describe("Frita agent integration", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  ctx.maybeTest(
    "letta-code can send a prompt to Frita by agent ID",
    async () => {
      const logger = await ctx.createLogger("FritaTestLogger_2026");
      await logger.clearLogs("Frita test ready.");

      const prompt =
        "This is an automated integration test. Reply with a short greeting and include the exact token FRITA_TEST_OK.";

      await logger.log(
        "Test started: letta-code can send a prompt to Frita by agent ID",
      );
      await logger.log(`Agent ID: ${FritaAgent.agentId}`);

      const runner = ctx.createJsonRunner({ conversation: "default" });
      const result = await runner.run(prompt);

      await logger.log(`CLI exited with code ${result.exitCode}`);

      if (result.exitCode !== 0) {
        await logger.log(
          `FAIL: exit code ${result.exitCode}. STDERR: ${result.stderr.slice(0, 500)}`,
        );
        throw new Error(
          `Expected exit code 0, got ${result.exitCode}.\nSTDERR:\n${result.stderr}`,
        );
      }

      const output = extractJsonObject(result.stdout);
      await logger.log(
        `JSON extracted. Keys: ${Object.keys(output).join(", ")}`,
      );

      expect(output.agent_id).toBe(FritaAgent.agentId);
      expect(typeof output.result).toBe("string");
      expect(String(output.result)).toContain("FRITA_TEST_OK");

      await logger.log("All assertions passed. Test complete.");
      await logger.flush();
    },
    { timeout: 190000 },
  );
});
