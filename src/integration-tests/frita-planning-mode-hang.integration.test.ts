/**
 * Integration test: Frita planning mode starvation detection.
 * Mirrors scissari-planning-mode-hang: detects output starvation (no new bytes
 * for 45 s) that indicates a silent hang during extended model thinking.
 *
 * To run: LETTA_RUN_FRITA_TEST=1 bun test frita-planning-mode-hang
 */

import { beforeEach, describe, expect } from "bun:test";
import { AgentTestContext } from "./framework/AgentTestContext";
import { FritaAgent } from "./framework/agents/FritaAgent";
import type { StarvationRunResult } from "./framework/runners/StarvationRunner";
import { resetAllLoggers } from "./logger-helpers";

const ctx = new AgentTestContext(FritaAgent);
const STARVATION_TIMEOUT_MS = 45_000;
const MAX_TOTAL_TIME_MS = 120_000;

describe("Frita planning mode hang detection", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  ctx.maybeTest(
    "detects output starvation during planning mode",
    async () => {
      const logger = await ctx.createLogger(
        "FritaPlanningModeHang_2026",
        "frita-hang",
      );
      await logger.clearLogs(
        "Frita planning mode hang detection test started.",
      );
      await logger.log(
        "Test started: detect output starvation during planning mode",
      );

      const runner = ctx.createStarvationRunner({
        starvationTimeoutMs: STARVATION_TIMEOUT_MS,
        maxTotalTimeMs: MAX_TOTAL_TIME_MS,
      });

      const prompt =
        "Create a comprehensive implementation plan for a multi-agent system that can coordinate between three specialized agents (code review, testing, and deployment). Include architecture, data flows, and error handling strategy.";

      const result = (await runner.run(prompt)) as StarvationRunResult;

      await logger.log(`CLI exit code: ${result.exitCode}`);
      await logger.log(`Has output: ${result.hasOutput}`);
      await logger.log(`Output starvation detected: ${result.starved}`);

      if (!result.hasOutput) {
        await logger.log("ERROR: CLI produced no output.");
        throw new Error(
          `Frita CLI exited with code ${result.exitCode} but produced no output.`,
        );
      }
      if (result.starved) {
        await logger.log(
          `ERROR: HANG DETECTED — no output for ${STARVATION_TIMEOUT_MS}ms`,
        );
        throw new Error(`Frita output starved for ${STARVATION_TIMEOUT_MS}ms`);
      }
      if (result.timedOut) {
        await logger.log(
          `ERROR: Process exceeded total time limit of ${MAX_TOTAL_TIME_MS}ms`,
        );
        throw new Error(
          `Frita CLI exceeded ${MAX_TOTAL_TIME_MS}ms total time limit`,
        );
      }

      expect(result.exitCode).toBe(0);

      const events = ctx.parser.parseLines(result.stdout);
      const final = ctx.parser.findFinalResult(events);
      if (final?.subtype !== "success") {
        await logger.log(
          `ERROR: Expected success result, got: ${final?.subtype}`,
        );
        throw new Error(
          `Expected result subtype "success", got "${final?.subtype ?? "unknown"}"`,
        );
      }

      const runIds = ctx.parser.extractRunIds(events);
      await logger.log(
        `PASS: completed successfully (${runIds.length} runs, exit=${result.exitCode})`,
      );
      await logger.flush();
    },
    { timeout: 90000 },
  );

  ctx.maybeTest(
    "recovers from partial thinking output without full hang",
    async () => {
      const logger = await ctx.createLogger(
        "FritaInactivityTimeout_2026",
        "frita-inactivity",
      );
      await logger.clearLogs("Frita inactivity recovery test starting.");
      await logger.log(
        "Test started: verify CLI completes after extended model thinking",
      );

      const runner = ctx.createStarvationRunner({
        starvationTimeoutMs: STARVATION_TIMEOUT_MS,
        maxTotalTimeMs: MAX_TOTAL_TIME_MS,
      });

      const prompt =
        "Analyze the trade-offs between microservices and monolithic architecture. Consider scalability, deployment, and team structure. Give a concise answer.";

      const result = (await runner.run(prompt)) as StarvationRunResult;

      await logger.log(`CLI exit code: ${result.exitCode}`);
      await logger.log(`Has output: ${result.hasOutput}`);
      await logger.log(`Output starvation detected: ${result.starved}`);

      if (!result.hasOutput) {
        await logger.log("ERROR: CLI produced no output.");
        throw new Error(
          `Frita CLI exited with code ${result.exitCode} but produced no output.`,
        );
      }
      if (result.starved) {
        await logger.log(
          `ERROR: STARVATION DETECTED — no output for ${STARVATION_TIMEOUT_MS}ms`,
        );
        throw new Error(
          `Frita starvation timeout: no output for ${STARVATION_TIMEOUT_MS}ms`,
        );
      }
      if (result.timedOut) {
        await logger.log(
          `ERROR: Process exceeded total time limit of ${MAX_TOTAL_TIME_MS}ms`,
        );
        throw new Error(
          `Frita CLI exceeded ${MAX_TOTAL_TIME_MS}ms total time limit`,
        );
      }

      expect(result.exitCode).toBe(0);

      const events = ctx.parser.parseLines(result.stdout);
      const final = ctx.parser.findFinalResult(events);
      if (final?.subtype !== "success") {
        throw new Error(
          `Expected result subtype "success", got "${final?.subtype ?? "unknown"}"`,
        );
      }
      if (!String(final?.result ?? "")) {
        throw new Error("Final result text is empty");
      }

      const runIds = ctx.parser.extractRunIds(events);
      await logger.log(
        `PASS: completed without starvation (${runIds.length} runs, ${result.stdout.length} bytes)`,
      );
      await logger.flush();
    },
    { timeout: 90000 },
  );
});
