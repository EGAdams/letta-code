/**
 * Integration test for the post-approval tool-execution hang.
 *
 * Bug scenario (Letta 0.16.3 + Scissari):
 *   1. Agent requests a Bash/Python tool call.
 *   2. Server sends approval_request_message with end_turn
 *      → drainStream converts end_turn → requires_approval
 *      → approvalRequestEndedTurn=true
 *   3. User approves; tool executes and returns a result.
 *   4. Tool result is submitted back to the server as a user *message*
 *      (not an approval response) because approvalRequestEndedTurn=true.
 *   5. The continuation stream fails with stopReason="error" (×2 — initial
 *      + resume attempt in drainStreamWithResume).
 *   6. BUG: agent stays stuck showing "Scissari is processing..." indefinitely
 *      instead of surfacing an error or completing.
 *
 * This test detects the hang by asserting the session completes within
 * COMPLETION_TIMEOUT_MS (95 s), which covers one full inactivity-timer cycle.
 * If the agent enters a retry loop the test will time out and fail.
 *
 * To run: LETTA_RUN_SCISSARI_TEST=1 bun test scissari-tool-execution-hang
 */

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
const LOGGER_ID = "ScissariToolExecutionHang_2026";
const ERROR_PATH_LOGGER_ID = "ScissariToolExecutionHang_ErrorPath_2026";

// Prompt that reliably triggers a Python3/Bash tool call.
// Mirrors the original "system_mechanic" database-query scenario where the
// tool completes quickly but the continuation stream hangs.
const TOOL_TRIGGER_PROMPT =
  "Run this exact python3 command and show me the output: python3 -c \"print('tool_test_ok')\"";
const TOOL_TRIGGER_ERROR_PROMPT =
  "Run this exact command and show me the output: python - <<'PY'\nprint('tool_test_error_path')\nPY";

// How long to wait for the session to complete after tool execution.
// One 90 s inactivity-timer cycle is the minimum for the hang to become visible;
// 95 s means the test catches even a single stuck retry before the hard limit.
const COMPLETION_TIMEOUT_MS = 95_000;

// Hard outer limit — gives the test a bit of slack for process setup/teardown.
const TEST_HARD_LIMIT_MS = 130_000;

interface StreamLine {
  type: string;
  subtype?: string;
  request_id?: string;
  request?: { subtype?: string };
  event?: Record<string, unknown>;
  result?: string;
  [key: string]: unknown;
}

interface RunResult {
  success: boolean;
  timedOut: boolean;
  approvalSeen: boolean;
  toolResultSeen: boolean;
  elapsedMs: number;
  messages: StreamLine[];
}

async function runApprovalAndContinueTest(
  toolTriggerPrompt: string,
): Promise<RunResult> {
  const startTime = Date.now();

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
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--memfs-startup",
        "skip",
        // No --yolo: approvals required so we exercise the
        // approval → execute → continuation-stream path.
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
    let initReceived = false;
    let approvalSeen = false;
    let toolResultSeen = false;
    let promptSent = false;
    let settled = false;
    let timedOut = false;

    const finish = (success: boolean, isTimeout = false) => {
      if (settled) return;
      settled = true;
      timedOut = isTimeout;
      clearTimeout(completionTimer);
      clearTimeout(safetyTimer);
      try {
        proc.stdin?.end();
        proc.kill();
      } catch {
        // ignore cleanup errors
      }
      resolve({
        success,
        timedOut,
        approvalSeen,
        toolResultSeen,
        elapsedMs: Date.now() - startTime,
        messages,
      });
    };

    // Primary deadline: detect the hang at exactly one inactivity-timer cycle.
    const completionTimer = setTimeout(
      () => finish(false, true),
      COMPLETION_TIMEOUT_MS,
    );

    // Safety net to avoid zombie processes if the process outlives the timer.
    const safetyTimer = setTimeout(
      () => finish(false, true),
      COMPLETION_TIMEOUT_MS + 5_000,
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

      // Step 1: system:init → send the tool-trigger prompt.
      if (msg.type === "system" && msg.subtype === "init" && !initReceived) {
        initReceived = true;
        if (!promptSent) {
          promptSent = true;
          const userMsg = JSON.stringify({
            type: "user",
            message: { role: "user", content: toolTriggerPrompt },
          });
          proc.stdin?.write(`${userMsg}\n`);
        }
        return;
      }

      // Step 2: headless stream-json mode emits control_request(can_use_tool)
      // when a tool needs approval. Approve it so the tool executes.
      if (
        msg.type === "control_request" &&
        msg.request?.subtype === "can_use_tool"
      ) {
        approvalSeen = true;
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

      // Also detect approval_request_message stream chunks (older protocol variant).
      const evt = msg.event;
      if (
        msg.type === "stream_event" &&
        evt &&
        typeof evt === "object" &&
        evt.message_type === "approval_request_message"
      ) {
        approvalSeen = true;
        return;
      }

      // Detect tool_return_message — confirms the tool actually ran.
      if (
        msg.type === "stream_event" &&
        evt &&
        typeof evt === "object" &&
        evt.message_type === "tool_return_message"
      ) {
        toolResultSeen = true;
        return;
      }

      // Terminal states:
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

describe("Scissari post-approval tool-execution hang", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30_000);

  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" ? test : test.skip;

  maybeTest(
    "agent completes within timeout after tool approved and executed",
    async () => {
      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs("ScissariToolExecutionHang test started.");
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[tool-hang] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[tool-hang] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch {
          // best-effort; never let logging failures break the test
        }
      };

      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      await log(`Prompt: ${TOOL_TRIGGER_PROMPT}`);
      await log(`Completion time limit: ${COMPLETION_TIMEOUT_MS}ms`);

      const result = await runApprovalAndContinueTest(TOOL_TRIGGER_PROMPT);

      await log(
        `elapsed=${result.elapsedMs}ms approvalSeen=${result.approvalSeen} ` +
          `toolResultSeen=${result.toolResultSeen} timedOut=${result.timedOut} ` +
          `success=${result.success} messages=${result.messages.length}`,
      );

      // The approval must have been requested; if not, the prompt didn't
      // trigger a tool call and this test is inconclusive.
      if (!result.approvalSeen) {
        await log(
          "WARNING: no approval seen — prompt may not have triggered a tool call",
        );
      }
      expect(result.approvalSeen).toBe(true);

      // Core assertion: agent must NOT stay stuck processing indefinitely.
      //
      // Bug path (without fix):
      //   1. Tool result returned as user message (approvalRequestEndedTurn=true).
      //   2. Continuation stream: 90 s inactivity timer fires → controller.abort()
      //      → SDK throws → catch block sets stopReason="error" (not "cancelled").
      //   3. drainStreamWithResume retries → second "error".
      //   4. isRetriableError() returns true for connection-style errors
      //      → processConversation does `continue` → new stream → stuck again.
      //
      // With the fix the inactivity abort produces stopReason="cancelled",
      // which is not retriable, so the agent surfaces an error and stops.
      if (result.timedOut) {
        await log(
          `ERROR: agent timed out after ${result.elapsedMs}ms — ` +
            "stuck in post-approval processing loop (this is the bug)",
        );
      } else {
        await log(`PASS: agent completed in ${result.elapsedMs}ms`);
      }

      expect(result.timedOut).toBe(false);
      expect(result.success).toBe(true);
      if (loggerReady) await logger.flushLogs();
    },
    TEST_HARD_LIMIT_MS,
  );

  maybeTest(
    "agent does not hang when approved tool command fails",
    async () => {
      const logger = new RemoteLogger(ERROR_PATH_LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs(
          "ScissariToolExecutionHang error-path test started.",
        );
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[tool-hang:error-path] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[tool-hang:error-path] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch {
          // best-effort; never let logging failures break the test
        }
      };

      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      await log(`Prompt: ${TOOL_TRIGGER_ERROR_PROMPT}`);
      await log(`Completion time limit: ${COMPLETION_TIMEOUT_MS}ms`);

      const result = await runApprovalAndContinueTest(TOOL_TRIGGER_ERROR_PROMPT);

      await log(
        `elapsed=${result.elapsedMs}ms approvalSeen=${result.approvalSeen} ` +
          `toolResultSeen=${result.toolResultSeen} timedOut=${result.timedOut} ` +
          `success=${result.success} messages=${result.messages.length}`,
      );

      expect(result.approvalSeen).toBe(true);
      // toolResultSeen may be false if the tool returns an error or if the protocol
      // doesn't surface tool_return_message in all cases. The key assertion is that
      // the agent did not hang (timedOut=false), which is the bug this test detects.
      expect(result.timedOut).toBe(false);
      if (result.timedOut) {
        await log(
          `ERROR: agent timed out after ${result.elapsedMs}ms — ` +
            "stuck in post-approval processing loop (this is the bug)",
        );
      } else {
        await log(`PASS: agent completed in ${result.elapsedMs}ms`);
      }
      if (loggerReady) await logger.flushLogs();
    },
    TEST_HARD_LIMIT_MS,
  );
});
