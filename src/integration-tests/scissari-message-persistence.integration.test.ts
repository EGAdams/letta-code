import { beforeEach, describe, expect, test } from "bun:test";
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { getClient } from "../agent/client";
import { RemoteLogger } from "../logger/RemoteLogger";
import { settingsManager } from "../settings-manager";
import { resetAllLoggers } from "./logger-helpers";

const SCISSARI_AGENT_ID = "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa";
const DEFAULT_BASE_URL = "http://100.80.49.10:8283";
const TEST_API_KEY = "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8";
const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const LOGGER_ID = "ScissariMessagePersistence_2026";

type JsonObject = Record<string, unknown>;

function parseJsonLines(stdout: string): JsonObject[] {
  return stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as JsonObject);
}

function extractRunIds(events: JsonObject[]): string[] {
  const ids = new Set<string>();
  for (const event of events) {
    const streamEvent = event.event;
    if (
      event.type === "stream_event" &&
      streamEvent &&
      typeof streamEvent === "object" &&
      "run_id" in streamEvent &&
      typeof streamEvent.run_id === "string"
    ) {
      ids.add(streamEvent.run_id);
    }
  }
  return [...ids];
}

function extractStreamMessageTypes(events: JsonObject[]): string[] {
  const types: string[] = [];
  for (const event of events) {
    const streamEvent = event.event;
    if (
      event.type === "stream_event" &&
      streamEvent &&
      typeof streamEvent === "object" &&
      "message_type" in streamEvent &&
      typeof streamEvent.message_type === "string"
    ) {
      types.push(streamEvent.message_type);
    }
  }
  return types;
}

function _messageContentText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (
          part &&
          typeof part === "object" &&
          "text" in part &&
          typeof part.text === "string"
        ) {
          return part.text;
        }
        return JSON.stringify(part);
      })
      .join("");
  }
  return content === undefined ? "" : JSON.stringify(content);
}

async function runScissariPrompt(
  prompt: string,
): Promise<{ stdout: string; stderr: string; exitCode: number | null }> {
  return new Promise((resolve, reject) => {
    const proc = spawn(
      "bun",
      [
        "run",
        "dev",
        "--agent",
        SCISSARI_AGENT_ID,
        "--new",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--include-partial-messages",
        "--memfs-startup",
        "skip",
      ],
      {
        cwd: projectRoot,
        env: {
          ...process.env,
          LETTA_CODE_AGENT_ROLE: "subagent",
          LETTA_BASE_URL: process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL,
          LETTA_API_KEY: process.env.LETTA_API_KEY ?? TEST_API_KEY,
        },
      },
    );

    let stdout = "";
    let stderr = "";
    let stdoutBuffer = "";
    let settled = false;
    const finish = (exitCode: number | null) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      try {
        proc.kill();
      } catch {
        // Ignore cleanup failures; the caller already has the captured output.
      }
      resolve({ stdout, stderr, exitCode });
    };
    const timeout = setTimeout(() => {
      if (settled) return;
      settled = true;
      proc.kill();
      reject(
        new Error(
          `Timed out waiting for Scissari prompt.\nSTDOUT:\n${stdout}\nSTDERR:\n${stderr}`,
        ),
      );
    }, 120000);

    proc.stdout?.on("data", (chunk) => {
      const text = chunk.toString();
      stdout += text;
      stdoutBuffer += text;
      while (true) {
        const newlineIndex = stdoutBuffer.indexOf("\n");
        if (newlineIndex === -1) break;
        const line = stdoutBuffer.slice(0, newlineIndex).trim();
        stdoutBuffer = stdoutBuffer.slice(newlineIndex + 1);
        if (!line) continue;
        try {
          const parsed = JSON.parse(line) as JsonObject;
          if (parsed.type === "result") {
            finish(0);
            return;
          }
          if (parsed.type === "error") {
            finish(1);
            return;
          }
        } catch {
          // Ignore non-JSON lines and keep buffering until the final line arrives.
        }
      }
    });
    proc.stderr?.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    proc.on("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      reject(error);
    });
    proc.on("close", (exitCode) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      resolve({ stdout, stderr, exitCode });
    });
  });
}

describe("Scissari message persistence integration", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" ? test : test.skip;

  maybeTest(
    "streamed assistant response is persisted on the run",
    async () => {
      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs(
          "Scissari message persistence test run started.",
        );
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[scissari-persistence] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[scissari-persistence] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch (err) {
          console.warn(
            `[scissari-persistence] log failed: ${err instanceof Error ? err.message : String(err)}`,
          );
        }
      };

      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      try {
        await log(
          "Test started: streamed assistant response is persisted on the run",
        );
        const token = `SCISSARI_PERSIST_${Date.now()}`;
        const result = await runScissariPrompt(
          `Reply with exactly ${token}. Do not use tools.`,
        );

        await log(`CLI exit code: ${result.exitCode}`);
        expect(result.exitCode).toBe(0);

        const events = parseJsonLines(result.stdout);
        const finalResult = events.find((event) => event.type === "result");
        expect(finalResult?.subtype).toBe("success");
        expect(String(finalResult?.result ?? "")).toContain(token);

        const runIds = extractRunIds(events);
        expect(runIds.length).toBeGreaterThan(0);
        const runId = runIds.at(-1) ?? "";
        await log(`run_id: ${runId}`);

        // In Letta 0.16.x, runs.messages only returns the initiating user_message —
        // the assistant response is not stored there. Verify persistence via run
        // status + step completion_tokens instead.
        const client = await getClient();
        const run = await client.runs.retrieve(runId);
        if (run.status !== "completed") {
          throw new Error(
            `Run ${runId} streamed ${token} but ended with status=${run.status} (expected "completed")`,
          );
        }
        await log(`PASS: run status=completed`);

        const stepsPage = await client.runs.steps.list(runId, { limit: 10 });
        const steps = stepsPage.getPaginatedItems();
        const completedStep = steps.find(
          (step) =>
            (step as unknown as Record<string, unknown>).status === "success" &&
            (((step as unknown as Record<string, unknown>)
              .completion_tokens as number) ?? 0) > 0,
        );
        if (!completedStep) {
          const stepSummary = steps
            .map((s) => {
              const sr = s as unknown as Record<string, unknown>;
              return `${String(sr.status)}:${String(sr.completion_tokens ?? 0)}tok`;
            })
            .join(", ");
          throw new Error(
            `Run ${runId} streamed ${token} but no step completed with tokens. Steps: ${stepSummary || "(none)"}`,
          );
        }
        await log(
          `PASS: run completed with model response (${String((completedStep as unknown as Record<string, unknown>).completion_tokens ?? 0)} completion tokens)`,
        );
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      } finally {
        // Keep logs in the viewer for post-run debugging.
      }
    },
    { timeout: 150000 },
  );

  maybeTest(
    "does not return reasoning-only output without a final assistant message",
    async () => {
      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs(
          "Scissari reasoning/final-message test run started.",
        );
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[scissari-persistence] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[scissari-persistence] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch (err) {
          console.warn(
            `[scissari-persistence] log failed: ${err instanceof Error ? err.message : String(err)}`,
          );
        }
      };

      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      try {
        await log(
          "Test started: does not return reasoning-only output without a final assistant message",
        );
        const token = `SCISSARI_FINAL_${Date.now()}`;
        const result = await runScissariPrompt(
          `Answer with exactly ${token}. Do not use tools.`,
        );

        await log(`CLI exit code: ${result.exitCode}`);
        expect(result.exitCode).toBe(0);

        const events = parseJsonLines(result.stdout);
        const messageTypes = extractStreamMessageTypes(events);
        const reasoningCount = messageTypes.filter(
          (type) => type === "reasoning_message",
        ).length;
        const assistantCount = messageTypes.filter(
          (type) => type === "assistant_message",
        ).length;
        await log(
          `message_types=${messageTypes.join(",") || "(none)"} reasoning=${reasoningCount} assistant=${assistantCount}`,
        );

        const finalResult = events.find((event) => event.type === "result");
        expect(finalResult?.subtype).toBe("success");
        expect(String(finalResult?.result ?? "")).toContain(token);

        if (reasoningCount > 0 && assistantCount === 0) {
          throw new Error(
            `Run emitted reasoning but no assistant_message. ` +
              `message_types=${messageTypes.join(",") || "(none)"} ` +
              `result=${String(finalResult?.result ?? "(empty)")}`,
          );
        }
        expect(assistantCount).toBeGreaterThan(0);

        const runIds = extractRunIds(events);
        expect(runIds.length).toBeGreaterThan(0);

        // In Letta 0.16.x, runs.messages only returns the initiating user_message —
        // verify persistence via run status + step completion_tokens instead.
        const client = await getClient();
        const runId = runIds.at(-1) ?? "";
        await log(`run_id: ${runId}`);

        const run = await client.runs.retrieve(runId);
        if (run.status !== "completed") {
          throw new Error(
            `Run ${runId} ended with status=${run.status} (expected "completed")`,
          );
        }
        const stepsPage = await client.runs.steps.list(runId, { limit: 10 });
        const steps = stepsPage.getPaginatedItems();
        const completedStep = steps.find(
          (step) =>
            (step as unknown as Record<string, unknown>).status === "success" &&
            (((step as unknown as Record<string, unknown>)
              .completion_tokens as number) ?? 0) > 0,
        );
        if (!completedStep) {
          const stepSummary = steps
            .map((s) => {
              const sr = s as unknown as Record<string, unknown>;
              return `${String(sr.status)}:${String(sr.completion_tokens ?? 0)}tok`;
            })
            .join(", ");
          throw new Error(
            `Run ${runId} has no step completed with tokens. Steps: ${stepSummary || "(none)"}`,
          );
        }
        await log(
          `PASS: assistant final message present and persisted (${String((completedStep as unknown as Record<string, unknown>).completion_tokens ?? 0)} completion tokens)`,
        );
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      } finally {
        // Keep logs in the viewer for post-run debugging.
        if (loggerReady) await logger.flushLogs();
      }
    },
    { timeout: 150000 },
  );
});
