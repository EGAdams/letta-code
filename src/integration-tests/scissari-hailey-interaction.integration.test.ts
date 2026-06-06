import { beforeEach, describe, expect } from "bun:test";
import { getClient } from "../agent/client";
import { AgentTestContext } from "./framework/AgentTestContext";
import { ScissariAgent } from "./framework/agents/ScissariAgent";
import { resetAllLoggers } from "./logger-helpers";

const ctx = new AgentTestContext(ScissariAgent);
const LOGGER_ID = "ScissariHaileyInteraction_2026";

function messageContentText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (
          part &&
          typeof part === "object" &&
          "text" in part &&
          typeof (part as Record<string, unknown>).text === "string"
        ) {
          return (part as Record<string, unknown>).text as string;
        }
        return JSON.stringify(part);
      })
      .join("");
  }
  return content === undefined ? "" : JSON.stringify(content);
}

describe("Scissari Hailey interaction integration", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  ctx.maybeTest(
    "Scissari can ask Hailey and return a final user-facing answer",
    async () => {
      await ctx.initSettings();
      const logger = await ctx.createLogger(LOGGER_ID, "scissari-hailey");
      await logger.clearLogs("Scissari Hailey interaction test run started.");

      try {
        const token = `SCISSARI_HAILEY_INTERACTION_${Date.now()}`;
        const runner = ctx.createStreamRunner({
          new: true,
          yolo: true,
          timeoutMs: 150000,
        });
        const result = await runner.run(
          `Please ask Hailey how the finance report is going and what we are working on specifically, then summarize her answer for me. Include diagnostic token ${token} in your final answer.`,
        );

        await logger.log(`CLI exit code: ${result.exitCode}`);
        expect(result.exitCode).toBe(0);

        const events = ctx.parser.parseLines(result.stdout);
        const final = ctx.parser.findFinalResult(events);
        const finalText = String(final?.result ?? "");
        await logger.log(`final result preview: ${finalText.slice(0, 300)}`);

        expect(final?.subtype).toBe("success");
        expect(finalText).toContain(token);
        expect(finalText).toContain("Hailey");
        expect(finalText).not.toContain("no assistant reply was returned");
        await logger.log("PASS: Scissari returned Hailey's answer to the user");
      } catch (err) {
        await logger.log(
          `ERROR: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      }
    },
    { timeout: 180000 },
  );

  ctx.maybeTest(
    "Scissari stream includes a successful synthetic tool return for Hailey",
    async () => {
      await ctx.initSettings();
      const logger = await ctx.createLogger(LOGGER_ID, "scissari-hailey");
      await logger.clearLogs(
        "Scissari Hailey tool-return interaction test run started.",
      );

      try {
        const token = `SCISSARI_HAILEY_TOOLRETURN_${Date.now()}`;
        const runner = ctx.createStreamRunner({
          new: true,
          yolo: true,
          timeoutMs: 150000,
        });
        const result = await runner.run(
          `Ask Hailey for a concise finance report status update and include diagnostic token ${token} in the final answer.`,
        );

        await logger.log(`CLI exit code: ${result.exitCode}`);
        expect(result.exitCode).toBe(0);

        const events = ctx.parser.parseLines(result.stdout);
        const toolReturns = ctx.parser.extractToolReturnEvents(events);
        const successfulReturn = toolReturns.find((ev) => {
          const se = ev.event as Record<string, unknown>;
          return (
            se.status === "success" &&
            String(se.tool_return ?? "").includes("Hailey replied:")
          );
        });

        if (!successfulReturn) {
          throw new Error(
            `No successful Hailey tool_return_message found. tool_returns=${JSON.stringify(toolReturns).slice(0, 1000)}`,
          );
        }

        const runIds = ctx.parser.extractRunIds(events);
        expect(runIds.length).toBeGreaterThan(0);
        await logger.log(`run_ids: ${runIds.join(",")}`);

        const client = await getClient();
        const persistedRuns: string[] = [];
        for (const runId of runIds) {
          const page = await client.runs.messages.list(runId, { limit: 50 });
          const matched = page
            .getPaginatedItems()
            .some((m) =>
              messageContentText(
                (m as unknown as Record<string, unknown>).content,
              ).includes("Hailey replied:"),
            );
          if (matched) persistedRuns.push(runId);
        }

        expect(persistedRuns.length).toBeGreaterThan(0);
        await logger.log(
          `PASS: tool_return_message seen and persisted on runs ${persistedRuns.join(",")}`,
        );
      } catch (err) {
        await logger.log(
          `ERROR: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      }
      await logger.flush();
    },
    { timeout: 180000 },
  );
});
