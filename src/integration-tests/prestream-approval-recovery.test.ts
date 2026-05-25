import { beforeEach, describe, expect, test } from "bun:test";
import { type ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { RemoteLogger } from "../logger/RemoteLogger";
import { resetAllLoggers } from "./logger-helpers";

const TOOL_TRIGGER_PROMPT =
  "Use the ShellCommand tool exactly once with command: touch /tmp/letta-code-prestream-approval-test. Do not ask clarifying questions.";
const FOLLOWUP_PROMPT = "Say OK only. Do not call tools.";

const normalizeLoggerMessage = (message: string): string => {
  if (message.includes("ERROR")) return message;
  if (/\bFAIL(?:ED)?\b/.test(message)) return `ERROR: ${message}`;
  if (
    /\bPASS(?:ED)?\b/.test(message) ||
    /test complete|test finished/i.test(message)
  ) {
    return message.includes("finished") ? message : `${message} finished`;
  }
  return message;
};

interface StreamMessage {
  type?: string;
  subtype?: string;
  message_type?: string;
  recovery_type?: string;
  conversation_id?: string;
  request?: { subtype?: string };
  [key: string]: unknown;
}

interface PendingApprovalSession {
  conversationId: string;
  stop: () => void;
  messages: StreamMessage[];
}

function parseJsonLines(text: string): StreamMessage[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .flatMap((line) => {
      try {
        return [JSON.parse(line) as StreamMessage];
      } catch {
        return [];
      }
    });
}

async function startPendingApprovalSession(
  timeoutMs = 300000, // Increased timeout to 5 minutes
): Promise<PendingApprovalSession> {
  return new Promise((resolve, reject) => {
    const proc: ChildProcessWithoutNullStreams = spawn(
      "bun",
      [
        "run",
        "dev",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--new-agent",
        "--new",
        "-m",
        "gpt-5.4-mini-plus-pro-medium",
      ],
      {
        cwd: process.cwd(),
        env: { ...process.env, LETTA_CODE_AGENT_ROLE: "subagent" },
      },
    );

    let stdoutBuffer = "";
    let stderrBuffer = "";
    const messages: StreamMessage[] = [];

    let settled = false;
    let conversationId: string | undefined;
    let promptAttempts = 0;
    let resultCount = 0;

    const sendPrompt = () => {
      if (promptAttempts >= 3) return;
      promptAttempts += 1;
      proc.stdin.write(
        `${JSON.stringify({
          type: "user",
          message: { role: "user", content: TOOL_TRIGGER_PROMPT },
        })}\n`,
      );
    };

    const stop = () => {
      proc.stdin.end();
      proc.kill();
    };

    const timeout = setTimeout(() => {
      if (settled) return;
      settled = true;
      stop();
      reject(
        new Error(
          `Timed out waiting for pending approval after ${timeoutMs}ms\nSTDERR:\n${stderrBuffer}`,
        ),
      );
    }, timeoutMs);

    const complete = () => {
      if (!conversationId) {
        settled = true;
        clearTimeout(timeout);
        stop();
        reject(
          new Error(
            "Pending approval detected before conversation ID was known",
          ),
        );
        return;
      }
      settled = true;
      clearTimeout(timeout);
      resolve({ conversationId, stop, messages });
    };

    const onMessage = (msg: StreamMessage) => {
      messages.push(msg);
      if (msg.type === "control_request") {
        console.log(
          `[startPendingApprovalSession] Received control_request: ${JSON.stringify(msg)}`,
        );
      }

      if (
        msg.type === "system" &&
        msg.subtype === "init" &&
        typeof msg.conversation_id === "string"
      ) {
        conversationId = msg.conversation_id;
        sendPrompt();
        return;
      }

      if (msg.type === "result") {
        resultCount += 1;
        if (promptAttempts < 3) {
          sendPrompt();
          return;
        }
        settled = true;
        clearTimeout(timeout);
        stop();
        reject(
          new Error(
            `Tool trigger prompt produced ${resultCount} result event(s) without a pending approval`,
          ),
        );
        return;
      }

      if (
        (msg.type === "control_request" &&
          msg.request?.subtype === "can_use_tool") ||
        msg.message_type === "approval_request_message"
      ) {
        complete();
      }
    };

    proc.stdout.on("data", (data) => {
      stdoutBuffer += data.toString();
      const lines = stdoutBuffer.split(/\r?\n/);
      stdoutBuffer = lines.pop() || "";

      for (const line of lines) {
        try {
          onMessage(JSON.parse(line));
        } catch {
          // Ignore non-JSON output lines
        }
      }
    });

    proc.stderr.on("data", (data) => {
      stderrBuffer += data.toString();
    });

    proc.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      reject(
        new Error(
          `Pending-approval process exited early (code=${code ?? "null"})\nSTDERR:\n${stderrBuffer}`,
        ),
      );
    });

    proc.on("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      reject(error);
    });
  });
}

async function runOneShotAgainstConversation(
  conversationId: string,
  timeoutMs = 180000,
): Promise<{ code: number | null; messages: StreamMessage[]; stderr: string }> {
  return new Promise((resolve, reject) => {
    const proc = spawn(
      "bun",
      [
        "run",
        "dev",
        "-p",
        FOLLOWUP_PROMPT,
        "--conversation",
        conversationId,
        "--output-format",
        "stream-json",
      ],
      {
        cwd: process.cwd(),
        env: { ...process.env, LETTA_CODE_AGENT_ROLE: "subagent" },
      },
    );

    let stdout = "";
    let stderr = "";
    let settled = false;

    const timeout = setTimeout(() => {
      if (settled) return;
      settled = true;
      proc.kill();
      reject(
        new Error(`Timed out waiting for one-shot run after ${timeoutMs}ms`),
      );
    }, timeoutMs);

    proc.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    proc.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    proc.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      resolve({ code, messages: parseJsonLines(stdout), stderr });
    });

    proc.on("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      reject(error);
    });
  });
}

describe("pre-stream approval recovery", () => {
  const maybeTest =
    process.env.LETTA_RUN_PRESTREAM_APPROVAL_RECOVERY_TEST === "1"
      ? test
      : test.skip;

  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  maybeTest(
    "recovers from pre-stream approval conflict and retries successfully",
    async () => {
      const logger = new RemoteLogger("PrestreamApproval_Recovery_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[prestream-approval] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[prestream-approval] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[prestream-approval] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      await log(
        "Test started: recovers from pre-stream approval conflict and retries successfully",
      );
      await log(`Tool trigger prompt: ${TOOL_TRIGGER_PROMPT}`);
      await log(`Followup prompt: ${FOLLOWUP_PROMPT}`);

      await log(
        "Phase 1: starting pending approval session (bidirectional mode, no --yolo)",
      );
      const pending = await startPendingApprovalSession();
      await log(
        `Phase 1 complete: conversationId=${pending.conversationId} messages=${pending.messages.length}`,
      );

      try {
        await log(
          "Phase 2: running one-shot against conversation with pending approval",
        );
        const result = await runOneShotAgainstConversation(
          pending.conversationId,
        );
        await log(
          `Phase 2 complete: exitCode=${result.code} messages=${result.messages.length}`,
        );

        if (result.code !== 0) {
          await log(
            `FAIL: one-shot run failed with exit code ${result.code}\nSTDERR: ${result.stderr.slice(0, 500)}`,
          );
          throw new Error(
            `Expected one-shot run to succeed, got exit code ${result.code}\nSTDERR:\n${result.stderr}`,
          );
        }
        await log("exit code 0: PASS");

        const recoveryEvent = result.messages.find(
          (m) =>
            m.type === "recovery" && m.recovery_type === "approval_pending",
        );
        await log(
          `recovery event found: ${
            recoveryEvent
              ? "YES"
              : "NO (pending approval was resolved before send)"
          }`,
        );

        const resultEvent = result.messages.find((m) => m.type === "result");
        await log(
          `result event found: ${resultEvent ? "YES" : "NO"} subtype=${resultEvent?.subtype}`,
        );
        expect(resultEvent).toBeDefined();
        expect(resultEvent?.subtype).toBe("success");

        await log("All assertions PASSED — test complete");
      } finally {
        pending.stop();
        await log("Pending session stopped after PASS");
        if (loggerReady) await logger.flushLogs();
      }
    },
    240000,
  );
});
