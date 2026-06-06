import { beforeEach, describe, expect } from "bun:test";
import { getClient } from "../agent/client";
import { AgentTestContext } from "./framework/AgentTestContext";
import { FritaAgent } from "./framework/agents/FritaAgent";
import { resetAllLoggers } from "./logger-helpers";

const ctx = new AgentTestContext(FritaAgent);
const LOGGER_ID = "FritaMessagePersistence_2026";

describe("Frita message persistence integration", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  ctx.maybeTest(
    "streamed assistant response is persisted on the run",
    async () => {
      await ctx.initSettings();
      const logger = await ctx.createLogger(LOGGER_ID, "frita-persistence");
      await logger.clearLogs("Frita message persistence test run started.");
      await logger.log(
        "Test started: streamed assistant response is persisted on the run",
      );

      try {
        const token = `FRITA_PERSIST_${Date.now()}`;
        const runner = ctx.createStreamRunner({ new: true });
        const result = await runner.run(
          `Reply with exactly ${token}. Do not use tools.`,
        );

        await logger.log(`CLI exit code: ${result.exitCode}`);
        expect(result.exitCode).toBe(0);

        const events = ctx.parser.parseLines(result.stdout);
        const final = ctx.parser.findFinalResult(events);
        expect(final?.subtype).toBe("success");
        expect(String(final?.result ?? "")).toContain(token);

        const runIds = ctx.parser.extractRunIds(events);
        expect(runIds.length).toBeGreaterThan(0);
        const runId = runIds.at(-1) ?? "";
        await logger.log(`run_id: ${runId}`);

        const client = await getClient();
        const run = await client.runs.retrieve(runId);
        if (run.status !== "completed") {
          throw new Error(
            `Run ${runId} streamed ${token} but ended with status=${run.status} (expected "completed")`,
          );
        }
        await logger.log("PASS: run status=completed");

        const stepsPage = await client.runs.steps.list(runId, { limit: 10 });
        const completedStep = stepsPage
          .getPaginatedItems()
          .find(
            (s) =>
              (s as unknown as Record<string, unknown>).status === "success" &&
              (((s as unknown as Record<string, unknown>)
                .completion_tokens as number) ?? 0) > 0,
          );
        if (!completedStep) {
          const summary = stepsPage
            .getPaginatedItems()
            .map((s) => {
              const r = s as unknown as Record<string, unknown>;
              return `${String(r.status)}:${String(r.completion_tokens ?? 0)}tok`;
            })
            .join(", ");
          throw new Error(
            `Run ${runId} has no step with completion tokens. Steps: ${summary || "(none)"}`,
          );
        }
        await logger.log("PASS: run completed with model response");
      } catch (err) {
        await logger.log(
          `ERROR: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        await logger.flush();
      }
    },
    { timeout: 150000 },
  );

  ctx.maybeTest(
    "does not return reasoning-only output without a final assistant message",
    async () => {
      await ctx.initSettings();
      const logger = await ctx.createLogger(LOGGER_ID, "frita-persistence");
      await logger.clearLogs("Frita reasoning/final-message test run started.");
      await logger.log(
        "Test started: does not return reasoning-only output without a final assistant message",
      );

      try {
        const token = `FRITA_FINAL_${Date.now()}`;
        const runner = ctx.createStreamRunner({ new: true });
        const result = await runner.run(
          `Answer with exactly ${token}. Do not use tools.`,
        );

        await logger.log(`CLI exit code: ${result.exitCode}`);
        expect(result.exitCode).toBe(0);

        const events = ctx.parser.parseLines(result.stdout);
        const messageTypes = ctx.parser.extractMessageTypes(events);
        const reasoningCount = messageTypes.filter(
          (t) => t === "reasoning_message",
        ).length;
        const assistantCount = messageTypes.filter(
          (t) => t === "assistant_message",
        ).length;
        await logger.log(
          `message_types=${messageTypes.join(",") || "(none)"} reasoning=${reasoningCount} assistant=${assistantCount}`,
        );

        const final = ctx.parser.findFinalResult(events);
        expect(final?.subtype).toBe("success");
        expect(String(final?.result ?? "")).toContain(token);

        if (reasoningCount > 0 && assistantCount === 0) {
          throw new Error(
            `Run emitted reasoning but no assistant_message. message_types=${messageTypes.join(",") || "(none)"}`,
          );
        }
        expect(assistantCount).toBeGreaterThan(0);

        const runIds = ctx.parser.extractRunIds(events);
        expect(runIds.length).toBeGreaterThan(0);

        const client = await getClient();
        const runId = runIds.at(-1) ?? "";
        const run = await client.runs.retrieve(runId);
        if (run.status !== "completed") {
          throw new Error(
            `Run ${runId} ended with status=${run.status} (expected "completed")`,
          );
        }
        const completedStep = (
          await client.runs.steps.list(runId, { limit: 10 })
        )
          .getPaginatedItems()
          .find(
            (s) =>
              (s as unknown as Record<string, unknown>).status === "success" &&
              (((s as unknown as Record<string, unknown>)
                .completion_tokens as number) ?? 0) > 0,
          );
        if (!completedStep) {
          throw new Error(`Run ${runId} has no step completed with tokens`);
        }
        await logger.log("PASS: assistant final message present and persisted");
      } catch (err) {
        await logger.log(
          `ERROR: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        await logger.flush();
      }
    },
    { timeout: 150000 },
  );
});
