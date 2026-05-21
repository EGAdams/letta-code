import { beforeEach, describe, expect, test } from "bun:test";
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { RemoteLogger } from "../logger/RemoteLogger";
import { settingsManager } from "../settings-manager";
import { resetAllLoggers } from "./logger-helpers";

const SCISSARI_AGENT_ID = "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa";
const DEFAULT_BASE_URL = "http://100.80.49.10:8283";
const TEST_API_KEY = "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8";
const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const LOGGER_ID = "ScissariSkillAdoptionToolCall_2026";

const TOOL_PROMPT =
  "adopt this skill: ```/home/adamsl/rol_finances/.claude/commands/find-duplicates.md``` If you already have not. Then run the commands `cat /home/adamsl/rol_finances/.claude/commands/find-duplicates.md`, `ls -la /home/adamsl/.letta/skills`, and `ls -la /home/adamsl/letta-code/skills`, and summarize exactly what you found.";

const COMPLETION_TIMEOUT_MS = 95_000;
const TEST_HARD_LIMIT_MS = 130_000;

interface StreamLine {
  type: string;
  subtype?: string;
  request_id?: string;
  request?: { subtype?: string };
  event?: Record<string, unknown>;
  [key: string]: unknown;
}

interface RunResult {
  success: boolean;
  timedOut: boolean;
  approvalCount: number;
  toolCallCount: number;
  toolReturnCount: number;
  endTurnStopReasons: number;
  messages: StreamLine[];
}

async function runSkillAdoptionFlow(): Promise<RunResult> {
  return new Promise<RunResult>((resolve, reject) => {
    const proc = spawn(
      "bun",
      [
        "run",
        "dev",
        "--agent",
        SCISSARI_AGENT_ID,
        "--new",
        "-p",
        TOOL_PROMPT,
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
          LETTA_DEBUG: "0",
        },
        stdio: ["pipe", "pipe", "pipe"],
      },
    );

    const messages: StreamLine[] = [];
    let stdoutBuffer = "";
    let settled = false;
    let approvalCount = 0;
    let toolCallCount = 0;
    let toolReturnCount = 0;
    let endTurnStopReasons = 0;

    const finish = (success: boolean, timedOut = false) => {
      if (settled) return;
      settled = true;
      clearTimeout(completionTimer);
      try {
        proc.stdin?.end();
        proc.kill();
      } catch {
        // ignore cleanup errors
      }
      resolve({
        success,
        timedOut,
        approvalCount,
        toolCallCount,
        toolReturnCount,
        endTurnStopReasons,
        messages,
      });
    };

    const completionTimer = setTimeout(
      () => finish(false, true),
      COMPLETION_TIMEOUT_MS,
    );

    const processLine = (line: string) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      let msg: StreamLine;
      try {
        msg = JSON.parse(trimmed) as StreamLine;
      } catch {
        return;
      }
      messages.push(msg);

      if (
        msg.type === "control_request" &&
        msg.request?.subtype === "can_use_tool"
      ) {
        approvalCount += 1;
        const requestId = msg.request_id;
        if (requestId) {
          const approveMsg = JSON.stringify({
            type: "control_response",
            response: {
              request_id: requestId,
              response: { behavior: "allow" },
            },
          });
          proc.stdin?.write(`${approveMsg}\n`);
        }
        return;
      }

      const evt = msg.event;
      if (msg.type === "stream_event" && evt && typeof evt === "object") {
        if (evt.message_type === "approval_request_message") {
          approvalCount += 1;
        }
        if (evt.message_type === "tool_call_message") {
          toolCallCount += 1;
        }
        if (evt.message_type === "tool_return_message") {
          toolReturnCount += 1;
        }
        if (
          evt.message_type === "stop_reason" &&
          evt.stop_reason === "end_turn"
        ) {
          endTurnStopReasons += 1;
        }
      }

      if (msg.type === "result") {
        finish(msg.subtype === "success");
        return;
      }
      if (msg.type === "error") {
        finish(false);
      }
    };

    proc.stdout?.on("data", (chunk: Buffer) => {
      stdoutBuffer += chunk.toString();
      const lines = stdoutBuffer.split("\n");
      stdoutBuffer = lines.pop() ?? "";
      for (const line of lines) processLine(line);
    });

    proc.on("close", () => {
      if (stdoutBuffer.trim()) processLine(stdoutBuffer);
      finish(false);
    });

    proc.on("error", (err) => {
      if (!settled) reject(err);
    });
  });
}

describe("Scissari skill adoption tool execution", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30_000);

  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" ? test : test.skip;

  maybeTest(
    "executes tool calls and returns tool output after approvals",
    async () => {
      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs(
          "Scissari skill adoption tool-call test started.",
        );
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[skill-adoption] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }

      const log = async (message: string) => {
        console.log(`[skill-adoption] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch {
          // best-effort only
        }
      };

      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      await log(`Prompt: ${TOOL_PROMPT}`);

      const result = await runSkillAdoptionFlow();

      await log(
        `success=${result.success} timedOut=${result.timedOut} approvals=${result.approvalCount} tool_call=${result.toolCallCount} tool_return=${result.toolReturnCount} end_turn=${result.endTurnStopReasons}`,
      );

      expect(result.timedOut).toBe(false);
      expect(result.success).toBe(true);
      expect(result.approvalCount).toBeGreaterThan(0);

      // Regression guard for the observed bug: approvals were seen,
      // but the run never emitted tool_call/tool_return lifecycle events.
      expect(result.toolCallCount).toBeGreaterThan(0);
      expect(result.toolReturnCount).toBeGreaterThan(0);
      if (loggerReady) await logger.flushLogs();
    },
    TEST_HARD_LIMIT_MS,
  );
});
