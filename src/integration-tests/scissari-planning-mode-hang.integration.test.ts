import { beforeEach, describe, test } from "bun:test";
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { RemoteLogger } from "../logger/RemoteLogger";
import { resetAllLoggers } from "./logger-helpers";

const SCISSARI_AGENT_ID = "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa";
const DEFAULT_BASE_URL = "http://100.80.49.10:8283";
const TEST_API_KEY = "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8";
const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

// Timeout for detecting output starvation (no new bytes for this long)
// Planning mode can be silent for extended periods, so use 45s threshold
const STARVATION_TIMEOUT_MS = 45000;
// Maximum total wait time for a prompt (planning mode can take 60+ seconds)
const MAX_TOTAL_TIME_MS = 120000;

type JsonObject = Record<string, unknown>;

function parseJsonLines(stdout: string): JsonObject[] {
  return stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as JsonObject;
      } catch {
        return null;
      }
    })
    .filter((obj): obj is JsonObject => obj !== null);
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

async function runScissariPromptWithStarvationDetection(
  prompt: string,
): Promise<{
  stdout: string;
  stderr: string;
  exitCode: number | null;
  starved: boolean;
  timedOut: boolean;
  starvationMs: number;
  hasOutput: boolean;
}> {
  return new Promise((resolve, reject) => {
    const proc = spawn(
      "bun",
      [
        "run",
        "dev",
        "--agent",
        SCISSARI_AGENT_ID,
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
    let lastOutputTime = Date.now();
    let starved = false;
    let timedOut = false;
    let starvationDetectionTime = 0;
    let hasOutput = false;
    let processClosed = false;

    const starvationTimer = setInterval(() => {
      const timeSinceLastOutput = Date.now() - lastOutputTime;
      // Only mark as starved if:
      // 1. We've received some output (hasOutput = true)
      // 2. No output for STARVATION_TIMEOUT_MS
      // 3. Not already starved
      if (
        hasOutput &&
        timeSinceLastOutput > STARVATION_TIMEOUT_MS &&
        !starved
      ) {
        starved = true;
        starvationDetectionTime = Date.now();
        proc.kill();
      }
    }, 1000);

    const totalTimeoutTimer = setTimeout(() => {
      // Only kill if process is still running (hasn't exited naturally)
      if (!processClosed) {
        timedOut = true;
        proc.kill();
      }
    }, MAX_TOTAL_TIME_MS);

    proc.stdout?.on("data", (chunk) => {
      lastOutputTime = Date.now();
      stdout += chunk.toString();
      hasOutput = true;
    });

    proc.stderr?.on("data", (chunk) => {
      lastOutputTime = Date.now();
      stderr += chunk.toString();
    });

    proc.on("error", (error) => {
      clearInterval(starvationTimer);
      clearTimeout(totalTimeoutTimer);
      reject(error);
    });

    proc.on("close", (code, signal) => {
      processClosed = true;
      clearInterval(starvationTimer);
      clearTimeout(totalTimeoutTimer);
      const finalStarvationMs = starved
        ? Date.now() - starvationDetectionTime
        : Date.now() - lastOutputTime;

      // If killed by signal, code is null; convert to exit code for consistency
      const exitCode = code !== null ? code : signal ? 128 + 15 : -1;

      resolve({
        stdout,
        stderr,
        exitCode,
        starved,
        timedOut,
        starvationMs: finalStarvationMs,
        hasOutput,
      });
    });
  });
}

describe("Scissari planning mode hang detection", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" ? test : test.skip;

  maybeTest(
    "detects output starvation during planning mode",
    async () => {
      const logger = new RemoteLogger("ScissariPlanningModeHang_2026");
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs(
          "Scissari planning mode hang detection test started.",
        );
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[scissari-hang] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }

      const log = async (message: string) => {
        console.log(`[scissari-hang] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch (err) {
          console.warn(
            `[scissari-hang] log failed: ${err instanceof Error ? err.message : String(err)}`,
          );
        }
      };

      try {
        await log(
          "Test started: detect output starvation during planning mode",
        );

        // Prompt that is likely to trigger Planning mode (complex task)
        const prompt =
          "Create a comprehensive implementation plan for a multi-agent system that can coordinate between three specialized agents (code review, testing, and deployment). Include architecture, data flows, and error handling strategy.";

        const result = await runScissariPromptWithStarvationDetection(prompt);

        await log(`CLI exit code: ${result.exitCode}`);
        await log(`Has output: ${result.hasOutput}`);
        await log(`Output starvation detected: ${result.starved}`);
        await log(
          `Time since last output: ${result.starvationMs}ms (starvation threshold: ${STARVATION_TIMEOUT_MS}ms)`,
        );

        if (!result.hasOutput) {
          await log(`ERROR: CLI produced no output. Process may have crashed.`);
          await log(
            `Stderr (first 500 chars): ${result.stderr.substring(0, 500) || "(empty)"}`,
          );
          throw new Error(
            `Scissari CLI exited with code ${result.exitCode} but produced no output. This suggests a crash or immediate failure.`,
          );
        }

        if (result.starved) {
          await log(
            `ERROR: HANG DETECTED — no output for ${STARVATION_TIMEOUT_MS}ms`,
          );
          await log(
            `Last stdout (first 500 chars): ${result.stdout.substring(0, 500)}`,
          );
          await log(
            `Last stderr (first 500 chars): ${result.stderr.substring(0, 500)}`,
          );

          const events = parseJsonLines(result.stdout);
          const runIds = extractRunIds(events);
          if (runIds.length > 0) {
            await log(
              `Last known run_id: ${runIds.at(-1) || "(none)"} (total runs: ${runIds.length})`,
            );
          } else {
            await log("No run_id found in output");
          }

          throw new Error(
            `Scissari output starved for ${STARVATION_TIMEOUT_MS}ms. Last stdout: ${result.stdout.substring(0, 200)}`,
          );
        }

        // Process completed without starvation — verify it succeeded
        if (result.timedOut) {
          await log(
            `ERROR: Process exceeded total time limit of ${MAX_TOTAL_TIME_MS}ms (exit=${result.exitCode})`,
          );
          throw new Error(
            `Scissari CLI exceeded ${MAX_TOTAL_TIME_MS}ms total time limit without starvation detection`,
          );
        }

        if (result.exitCode !== 0) {
          await log(
            `ERROR: CLI exited with unexpected code ${result.exitCode}. Stderr: ${result.stderr.substring(0, 300) || "(empty)"}`,
          );
          throw new Error(`Expected exit code 0, got ${result.exitCode}`);
        }

        const events = parseJsonLines(result.stdout);
        const finalResult = events.find((event) => event.type === "result");

        if (finalResult?.subtype !== "success") {
          await log(
            `ERROR: Expected success result, got: ${finalResult?.subtype}`,
          );
          throw new Error(
            `Expected result subtype "success", got "${finalResult?.subtype || "unknown"}"`,
          );
        }

        const runIds = extractRunIds(events);
        await log(
          `PASS: completed successfully (${runIds.length} runs, exit=${result.exitCode})`,
        );
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      }
    },
    { timeout: 90000 },
  );

  maybeTest(
    "recovers from partial thinking output without full hang",
    async () => {
      const logger = new RemoteLogger("ScissariInactivityTimeout_2026");
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs("Scissari inactivity recovery test starting.");
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[scissari-inactivity] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }

      const log = async (message: string) => {
        console.log(`[scissari-inactivity] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch (err) {
          console.warn(
            `[scissari-inactivity] log failed: ${err instanceof Error ? err.message : String(err)}`,
          );
        }
      };

      try {
        await log(
          "Test started: verify CLI completes after extended model thinking",
        );

        // Prompt that might cause extended thinking but should still complete
        const prompt =
          "Analyze the trade-offs between microservices and monolithic architecture. Consider scalability, deployment, and team structure. Give a concise answer.";

        const result = await runScissariPromptWithStarvationDetection(prompt);

        await log(`CLI exit code: ${result.exitCode}`);
        await log(`Has output: ${result.hasOutput}`);
        await log(`Output starvation detected: ${result.starved}`);
        await log(
          `Time since last output: ${result.starvationMs}ms (starvation threshold: ${STARVATION_TIMEOUT_MS}ms)`,
        );

        if (!result.hasOutput) {
          await log(`ERROR: CLI produced no output. Process may have crashed.`);
          await log(
            `Stderr (first 500 chars): ${result.stderr.substring(0, 500) || "(empty)"}`,
          );
          throw new Error(
            `Scissari CLI exited with code ${result.exitCode} but produced no output.`,
          );
        }

        if (result.starved) {
          await log(
            `ERROR: STARVATION DETECTED — process hung for ${STARVATION_TIMEOUT_MS}ms`,
          );
          await log(
            `Last stdout (first 300 chars): ${result.stdout.substring(0, 300)}`,
          );
          throw new Error(
            `Scissari starvation timeout: no output for ${STARVATION_TIMEOUT_MS}ms`,
          );
        }

        if (result.timedOut) {
          await log(
            `ERROR: Process exceeded total time limit of ${MAX_TOTAL_TIME_MS}ms (exit=${result.exitCode})`,
          );
          throw new Error(
            `Scissari CLI exceeded ${MAX_TOTAL_TIME_MS}ms total time limit`,
          );
        }

        if (result.exitCode !== 0) {
          await log(
            `ERROR: CLI exited with unexpected code ${result.exitCode}. Stderr: ${result.stderr.substring(0, 300) || "(empty)"}`,
          );
          throw new Error(`Expected exit code 0, got ${result.exitCode}`);
        }

        const events = parseJsonLines(result.stdout);
        const finalResult = events.find((event) => event.type === "result");

        if (finalResult?.subtype !== "success") {
          await log(
            `ERROR: Expected success result, got: ${finalResult?.subtype}`,
          );
          throw new Error(
            `Expected result subtype "success", got "${finalResult?.subtype || "unknown"}"`,
          );
        }

        if (!String(finalResult?.result || "")) {
          await log("ERROR: Final result text is empty");
          throw new Error("Final result text is empty");
        }

        const runIds = extractRunIds(events);
        await log(
          `PASS: completed without starvation (${runIds.length} runs, ${result.stdout.length} bytes output)`,
        );
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      }
      if (loggerReady) await logger.flushLogs();
    },
    { timeout: 90000 },
  );
});
