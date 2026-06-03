/**
 * Integration test: Frita post-approval tool-execution hang detection.
 * Mirrors scissari-tool-execution-hang: asserts the session completes within
 * COMPLETION_TIMEOUT_MS after a tool is approved and executed.
 *
 * To run: LETTA_RUN_FRITA_TEST=1 bun test frita-tool-execution-hang
 */

import { beforeEach, describe, expect } from "bun:test";
import { AgentTestContext } from "./framework/AgentTestContext";
import { FritaAgent } from "./framework/agents/FritaAgent";
import type { BidirectionalRunResult } from "./framework/runners/BidirectionalRunner";
import { resetAllLoggers } from "./logger-helpers";

const ctx = new AgentTestContext(FritaAgent);

const TOOL_TRIGGER_PROMPT =
  "Run this exact python3 command and show me the output: python3 -c \"print('tool_test_ok')\"";
const TOOL_TRIGGER_ERROR_PROMPT =
  "Run this exact command and show me the output: python - <<'PY'\nprint('tool_test_error_path')\nPY";

const COMPLETION_TIMEOUT_MS = 95_000;
const TEST_HARD_LIMIT_MS = 130_000;

describe("Frita post-approval tool-execution hang", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30_000);

  ctx.maybeTest(
    "agent completes within timeout after tool approved and executed",
    async () => {
      await ctx.initSettings();
      const logger = await ctx.createLogger(
        "FritaToolExecutionHang_2026",
        "frita-tool-hang",
      );
      await logger.clearLogs("FritaToolExecutionHang test started.");

      await logger.log(`Prompt: ${TOOL_TRIGGER_PROMPT}`);
      await logger.log(`Completion time limit: ${COMPLETION_TIMEOUT_MS}ms`);

      const runner = ctx.createBidirectionalRunner({
        timeoutMs: COMPLETION_TIMEOUT_MS,
      });
      const result = (await runner.run(
        TOOL_TRIGGER_PROMPT,
      )) as BidirectionalRunResult;

      await logger.log(
        `elapsed=${result.elapsedMs}ms approvalCount=${result.approvalCount} ` +
          `toolReturnCount=${result.toolReturnCount} timedOut=${result.timedOut} ` +
          `success=${result.success} messages=${result.messages.length}`,
      );

      if (!result.approvalCount) {
        await logger.log(
          "INFO: no client-side approval seen — agent used a server-side tool (executor_run)",
        );
      }

      if (result.timedOut) {
        await logger.log(
          `ERROR: agent timed out after ${result.elapsedMs}ms — stuck in post-approval processing loop`,
        );
      } else {
        await logger.log(`PASS: agent completed in ${result.elapsedMs}ms`);
      }

      expect(result.timedOut).toBe(false);
      expect(result.success).toBe(true);
      await logger.flush();
    },
    TEST_HARD_LIMIT_MS,
  );

  ctx.maybeTest(
    "agent does not hang when approved tool command fails",
    async () => {
      await ctx.initSettings();
      const logger = await ctx.createLogger(
        "FritaToolExecutionHang_ErrorPath_2026",
        "frita-tool-hang:error-path",
      );
      await logger.clearLogs("FritaToolExecutionHang error-path test started.");

      await logger.log(`Prompt: ${TOOL_TRIGGER_ERROR_PROMPT}`);

      const runner = ctx.createBidirectionalRunner({
        timeoutMs: COMPLETION_TIMEOUT_MS,
      });
      const result = (await runner.run(
        TOOL_TRIGGER_ERROR_PROMPT,
      )) as BidirectionalRunResult;

      await logger.log(
        `elapsed=${result.elapsedMs}ms approvalCount=${result.approvalCount} ` +
          `toolReturnCount=${result.toolReturnCount} timedOut=${result.timedOut} ` +
          `success=${result.success} messages=${result.messages.length}`,
      );

      if (!result.approvalCount) {
        await logger.log(
          "INFO: no client-side approval seen — agent used a server-side tool (executor_run)",
        );
      }

      expect(result.timedOut).toBe(false);
      if (result.timedOut) {
        await logger.log(`ERROR: agent timed out after ${result.elapsedMs}ms`);
      } else {
        await logger.log(`PASS: agent completed in ${result.elapsedMs}ms`);
      }
      await logger.flush();
    },
    TEST_HARD_LIMIT_MS,
  );
});
