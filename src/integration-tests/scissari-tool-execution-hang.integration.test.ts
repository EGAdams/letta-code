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
const LOGGER_ID = "ScissariToolExecutionHang_2026";

// If reasoning runs this long without a tool_call_message, declare it a hang.
// The root cause: the 90s inactivity timer in stream.ts resets on reasoning_message
// chunks, so planning loops forever without executing tools.
const REASONING_WITHOUT_TOOL_TIMEOUT_MS = 60_000;
const MAX_TOTAL_TIME_MS = 150_000;

type JsonObject = Record<string, unknown>;

async function runScissariAndWatchStream(prompt: string): Promise<{
  stdout: string;
  stderr: string;
  exitCode: number | null;
  messageTypes: string[];
  stopReasons: string[];
  reasoningOnlyHang: boolean;
  timedOut: boolean;
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
    let stdoutBuffer = "";
    let hasOutput = false;
    let processClosed = false;
    let reasoningOnlyHang = false;
    let timedOut = false;
    const messageTypes: string[] = [];
    const stopReasons: string[] = [];

    let firstReasoningMs: number | null = null;
    let hasSeenToolOrAssistant = false;

    const hangDetectionTimer = setInterval(() => {
      if (hasSeenToolOrAssistant || firstReasoningMs === null) return;
      const elapsed = Date.now() - firstReasoningMs;
      if (elapsed > REASONING_WITHOUT_TOOL_TIMEOUT_MS && !reasoningOnlyHang) {
        reasoningOnlyHang = true;
        clearInterval(hangDetectionTimer);
        clearTimeout(totalTimeoutTimer);
        proc.kill();
      }
    }, 1000);

    const totalTimeoutTimer = setTimeout(() => {
      if (!processClosed) {
        timedOut = true;
        clearInterval(hangDetectionTimer);
        proc.kill();
      }
    }, MAX_TOTAL_TIME_MS);

    proc.stdout?.on("data", (chunk) => {
      const text = chunk.toString();
      stdout += text;
      stdoutBuffer += text;
      hasOutput = true;

      while (true) {
        const newlineIndex = stdoutBuffer.indexOf("\n");
        if (newlineIndex === -1) break;
        const line = stdoutBuffer.slice(0, newlineIndex).trim();
        stdoutBuffer = stdoutBuffer.slice(newlineIndex + 1);
        if (!line) continue;
        try {
          const parsed = JSON.parse(line) as JsonObject;
          const streamEvent = parsed.event;
          if (
            parsed.type === "stream_event" &&
            streamEvent &&
            typeof streamEvent === "object" &&
            "message_type" in streamEvent &&
            typeof streamEvent.message_type === "string"
          ) {
            const msgType = streamEvent.message_type as string;
            messageTypes.push(msgType);

            if (msgType === "reasoning_message" && firstReasoningMs === null) {
              firstReasoningMs = Date.now();
            }
            if (
              msgType === "tool_call_message" ||
              msgType === "assistant_message"
            ) {
              hasSeenToolOrAssistant = true;
            }
          }
          // Track stop_reason values
          if (
            parsed.type === "stream_event" &&
            streamEvent &&
            typeof streamEvent === "object" &&
            "stop_reason" in streamEvent
          ) {
            const reason = streamEvent.stop_reason as string;
            if (reason) stopReasons.push(reason);
          }
        } catch {
          // non-JSON lines are fine
        }
      }
    });

    proc.stderr?.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    proc.on("error", (error) => {
      clearInterval(hangDetectionTimer);
      clearTimeout(totalTimeoutTimer);
      reject(error);
    });

    proc.on("close", (code, signal) => {
      processClosed = true;
      clearInterval(hangDetectionTimer);
      clearTimeout(totalTimeoutTimer);
      const exitCode = code !== null ? code : signal ? 128 + 15 : -1;
      resolve({
        stdout,
        stderr,
        exitCode,
        messageTypes,
        stopReasons,
        reasoningOnlyHang,
        timedOut,
        hasOutput,
      });
    });
  });
}

describe("Scissari tool execution hang detection", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" ? test : test.skip;

  maybeTest(
    "executes a tool call instead of looping in reasoning only",
    async () => {
      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs("Scissari tool execution hang test started.");
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[scissari-tool-hang] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }

      const log = async (message: string) => {
        console.log(`[scissari-tool-hang] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch (err) {
          console.warn(
            `[scissari-tool-hang] log failed: ${err instanceof Error ? err.message : String(err)}`,
          );
        }
      };

      try {
        await log(
          "Test started: Scissari should execute a tool call without looping in reasoning",
        );

        // Prompt that requires tool execution — mirrors the stuck-in-planning scenario
        // where Scissari was about to call Bash(python ...) but never did.
        const prompt =
          "Use the Bash tool to run `echo hello_from_scissari_tool_test` and return the output.";

        const result = await runScissariAndWatchStream(prompt);

        const reasoningCount = result.messageTypes.filter(
          (t) => t === "reasoning_message",
        ).length;
        const toolCallCount = result.messageTypes.filter(
          (t) => t === "tool_call_message",
        ).length;
        const assistantCount = result.messageTypes.filter(
          (t) => t === "assistant_message",
        ).length;

        await log(
          `Message types: ${result.messageTypes.join(",") || "(none)"}`,
        );
        await log(`Stop reasons: ${result.stopReasons.join(",") || "(none)"}`);
        await log(
          `reasoning=${reasoningCount} tool_call=${toolCallCount} assistant=${assistantCount}`,
        );
        await log(`Reasoning-only hang: ${result.reasoningOnlyHang}`);
        await log(`Has output: ${result.hasOutput}`);

        if (!result.hasOutput) {
          await log(`ERROR: CLI produced no output (exit=${result.exitCode})`);
          await log(`Stderr: ${result.stderr.substring(0, 500) || "(empty)"}`);
          throw new Error(
            `Scissari CLI exited with code ${result.exitCode} but produced no output.`,
          );
        }

        if (result.timedOut) {
          await log(
            `ERROR: Process exceeded total time limit of ${MAX_TOTAL_TIME_MS}ms`,
          );
          throw new Error(
            `Scissari CLI exceeded ${MAX_TOTAL_TIME_MS}ms total time limit`,
          );
        }

        if (result.reasoningOnlyHang) {
          await log(
            `ERROR: PLANNING LOOP DETECTED — reasoning_message for ${REASONING_WITHOUT_TOOL_TIMEOUT_MS}ms without any tool_call_message`,
          );
          await log(`reasoning=${reasoningCount} tool_call=${toolCallCount}`);
          throw new Error(
            `Scissari entered a planning loop: ${reasoningCount} reasoning chunks with no tool_call_message in ${REASONING_WITHOUT_TOOL_TIMEOUT_MS}ms. ` +
              `Root cause: 90s inactivity timer in stream.ts resets on reasoning_message, ` +
              `so the planning loop never triggers the timeout.`,
          );
        }

        // The core assertion: Scissari must actually execute the Bash tool.
        // Seeing only approval_request_message + assistant_message means she asked for
        // permission but then fell back to a text response without running the command.
        const toolReturnCount = result.messageTypes.filter(
          (t) => t === "tool_return_message",
        ).length;
        await log(`tool_return=${toolReturnCount}`);

        if (toolCallCount === 0 || toolReturnCount === 0) {
          await log(
            `ERROR: Bash tool was never executed — tool_call=${toolCallCount} tool_return=${toolReturnCount}`,
          );
          await log(
            `This is the stuck-on-tool-call bug: Scissari plans, asks for approval, then falls back to text without running the command.`,
          );
          throw new Error(
            `Scissari did not execute the Bash tool. ` +
              `tool_call=${toolCallCount} tool_return=${toolReturnCount} assistant=${assistantCount}. ` +
              `She asked for approval (approval_request=${result.messageTypes.filter((t) => t === "approval_request_message").length}) ` +
              `but the command never ran.`,
          );
        }

        if (result.exitCode !== 0) {
          await log(
            `ERROR: CLI exited with unexpected code ${result.exitCode}`,
          );
          throw new Error(`Expected exit code 0, got ${result.exitCode}`);
        }

        await log(
          `PASS: Scissari executed tool call (reasoning=${reasoningCount} tool_call=${toolCallCount} tool_return=${toolReturnCount})`,
        );
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      }
    },
    { timeout: 180000 },
  );
});
