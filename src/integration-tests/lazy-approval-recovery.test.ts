import { beforeEach, describe, expect, test } from "bun:test";
import { spawn } from "node:child_process";
import { RemoteLogger } from "../logger/RemoteLogger";
import { resetAllLoggers } from "./logger-helpers";

const TEST_TIMEOUT_MS = 30000;

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
const testWithTimeout = (
  name: string,
  fn: () => Promise<void> | void,
  opts?: { timeout?: number } | number,
) =>
  test(
    name,
    fn,
    typeof opts === "number" ? opts : (opts?.timeout ?? TEST_TIMEOUT_MS),
  );

/**
 * Integration test for lazy approval recovery (LET-7101).
 *
 * NOTE: The lazy approval recovery is primarily designed for TUI mode where:
 * 1. User has a session with pending approvals (e.g., from a previous run)
 * 2. User sends a new message before responding to the approval
 * 3. Server returns CONFLICT error
 * 4. CLI recovers by auto-denying stale approvals and retrying
 *
 * In bidirectional mode, messages sent during permission wait are dropped
 * (see headless.ts line 1710-1714), so we can't directly test the CONFLICT
 * scenario here. This test validates that the flow doesn't crash when
 * messages are sent while approvals are pending.
 *
 * The RecoveryMessage emission can be tested by:
 * 1. Manual testing in TUI mode (start session with orphaned approval)
 * 2. Or by modifying headless mode to not drop messages during permission wait
 */

// Prompt that will trigger a Bash tool call requiring approval
const BASH_TRIGGER_PROMPT =
  "Run this exact bash command: echo test123. Do not use any other tools.";

// Second message to send while approval is pending
const INTERRUPT_MESSAGE =
  "Actually, just say OK instead. Do not call any tools.";

interface StreamMessage {
  type: string;
  subtype?: string;
  message_type?: string;
  stop_reason?: string;
  request_id?: string;
  request?: { subtype?: string };
  // biome-ignore lint/suspicious/noExplicitAny: index signature for arbitrary JSON fields
  [key: string]: any;
}

/**
 * Run bidirectional test with custom message handling.
 * Allows sending messages at specific points in the flow.
 */
async function runLazyRecoveryTest(timeoutMs = 300000): Promise<{
  messages: StreamMessage[];
  success: boolean;
  errorSeen: boolean;
}> {
  return new Promise((resolve, reject) => {
    const proc = spawn(
      "bun",
      [
        "run",
        "dev",
        "-p",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--new-agent",
        "-m",
        "gpt-5.4-mini-plus-pro-medium",
        // NOTE: No --yolo flag - approvals are required
      ],
      {
        cwd: process.cwd(),
        // Mark as subagent to prevent polluting user's LRU settings
        env: { ...process.env, LETTA_CODE_AGENT_ROLE: "subagent" },
      },
    );

    const messages: StreamMessage[] = [];
    let buffer = "";
    let initReceived = false;
    let approvalSeen = false;
    let interruptSent = false;
    let errorSeen = false;
    let resultCount = 0;
    let closing = false;
    let pendingToolCallId: string | undefined;
    let promptAttempts = 0;

    const sendPrompt = () => {
      if (promptAttempts >= 3) return;
      promptAttempts++;
      const userMsg = JSON.stringify({
        type: "user",
        message: { role: "user", content: BASH_TRIGGER_PROMPT },
      });
      proc.stdin?.write(`${userMsg}\n`);
    };

    const timeout = setTimeout(() => {
      if (!closing) {
        proc.kill();
        reject(new Error(`Test timed out after ${timeoutMs}ms`));
      }
    }, timeoutMs);

    const cleanup = () => {
      closing = true;
      clearTimeout(timeout);
      setTimeout(() => {
        proc.stdin?.end();
        proc.kill();
      }, 500);
    };

    const processLine = (line: string) => {
      if (!line.trim()) return;
      try {
        const msg: StreamMessage = JSON.parse(line);
        messages.push(msg);

        // Debug output
        if (process.env.DEBUG_TEST) {
          console.log("MSG:", JSON.stringify(msg, null, 2));
        }

        // Handle permission control requests from headless.
        // In some runs, control_request can arrive even when approval stream chunks
        // are delayed or omitted, so respond directly to avoid deadlocks.
        if (
          msg.type === "control_request" &&
          msg.request?.subtype === "can_use_tool"
        ) {
          approvalSeen = true;
          const requestId = msg.request_id;
          if (requestId) {
            if (pendingToolCallId && !requestId.endsWith(pendingToolCallId)) {
              console.log(
                `Note: control_request id ${requestId} did not match expected tool id ${pendingToolCallId}`,
              );
            }

            // Send the interrupt message while approval is pending, then deny.
            if (!interruptSent) {
              interruptSent = true;
              const userMsg = JSON.stringify({
                type: "user",
                message: { role: "user", content: INTERRUPT_MESSAGE },
              });
              proc.stdin?.write(`${userMsg}\n`);
            }

            const denyApproval = JSON.stringify({
              type: "control_response",
              response: {
                request_id: requestId,
                response: {
                  behavior: "deny",
                  message:
                    "Denied by integration test to simulate stale approval",
                },
              },
            });
            proc.stdin?.write(`${denyApproval}\n`);
          }
          return;
        }

        // Step 1: Wait for init, then send bash trigger prompt
        if (msg.type === "system" && msg.subtype === "init" && !initReceived) {
          initReceived = true;
          sendPrompt();
          return;
        }

        // Step 2: When we see approval request, send another user message instead,
        // then explicitly deny the pending approval so the flow can complete in
        // headless stream-json mode (which waits for approval responses).
        if (
          msg.type === "message" &&
          msg.message_type === "approval_request_message" &&
          !approvalSeen
        ) {
          approvalSeen = true;

          const toolCall = Array.isArray(msg.tool_call)
            ? msg.tool_call[0]
            : msg.tool_call;
          pendingToolCallId =
            toolCall && typeof toolCall === "object"
              ? (toolCall as { tool_call_id?: string }).tool_call_id
              : undefined;

          // If approval stream chunks arrive before can_use_tool callback,
          // still send the concurrent user message now.
          if (!interruptSent) {
            interruptSent = true;
            const userMsg = JSON.stringify({
              type: "user",
              message: { role: "user", content: INTERRUPT_MESSAGE },
            });
            proc.stdin?.write(`${userMsg}\n`);
          }
          return;
        }

        // Track recovery messages - this is the key signal that lazy recovery worked
        if (
          msg.type === "recovery" &&
          msg.recovery_type === "approval_pending"
        ) {
          errorSeen = true; // reusing this flag to mean "recovery message seen"
        }

        // Also track raw errors (shouldn't see these if recovery works properly)
        if (
          msg.type === "error" ||
          (msg.type === "message" && msg.message_type === "error_message")
        ) {
          const detail = msg.detail || msg.message || "";
          if (detail.toLowerCase().includes("cannot send a new message")) {
            // Raw error leaked through - recovery may have failed
            console.log(
              "WARNING: Raw CONFLICT error seen (recovery may have failed)",
            );
          }
        }

        // Track results and complete once we prove the pending-approval flow unblocks.
        if (msg.type === "result") {
          resultCount++;
          // If model responded without calling a tool, retry prompt (up to 3 attempts)
          if (!approvalSeen && promptAttempts < 3) {
            sendPrompt();
            return;
          }
          if (resultCount >= 1 && !approvalSeen) {
            cleanup();
            resolve({ messages, success: false, errorSeen });
            return;
          }

          // One completed turn is enough once we have confirmed
          // approval flow + concurrent user message injection.
          if (
            resultCount >= 1 &&
            approvalSeen &&
            (interruptSent || errorSeen)
          ) {
            cleanup();
            resolve({ messages, success: true, errorSeen });
          }
        }
      } catch {
        // Not valid JSON, ignore
      }
    };

    proc.stdout?.on("data", (data) => {
      buffer += data.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        processLine(line);
      }
    });

    let _stderr = "";
    proc.stderr?.on("data", (data) => {
      _stderr += data.toString();
    });

    proc.on("close", (_code) => {
      clearTimeout(timeout);
      // Process any remaining buffer
      if (buffer.trim()) {
        processLine(buffer);
      }

      if (!closing) {
        // If we got here without resolving, check what we have
        resolve({
          messages,
          success: resultCount > 0,
          errorSeen,
        });
      }
    });

    proc.on("error", (err) => {
      clearTimeout(timeout);
      reject(err);
    });
  });
}

describe("lazy approval recovery", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  testWithTimeout(
    "handles concurrent message while approval is pending",
    async () => {
      const logger = new RemoteLogger("LazyApproval_ConcurrentMessage_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[lazy-approval] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[lazy-approval] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[lazy-approval] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      try {
        await log(
          "Test started: handles concurrent message while approval is pending",
        );
        await log(`Trigger prompt: ${BASH_TRIGGER_PROMPT}`);
        await log(`Interrupt message: ${INTERRUPT_MESSAGE}`);

        let result = await runLazyRecoveryTest();
        await log(
          `Attempt 1: success=${result.success} errorSeen=${result.errorSeen} messages=${result.messages.length}`,
        );

        if (!result.success) {
          await log(
            "Attempt 1 failed — retrying once for transient timing issues",
          );
          result = await runLazyRecoveryTest();
          await log(
            `Attempt 2: success=${result.success} errorSeen=${result.errorSeen} messages=${result.messages.length}`,
          );
        }

        if (!result.success) {
          await log(
            "FAIL: test did not succeed after retry — logging all messages",
          );
          for (const msg of result.messages) {
            console.log(JSON.stringify(msg, null, 2));
          }
        }

        const approvalSignal = result.messages.find(
          (m) =>
            m.message_type === "approval_request_message" ||
            (m.type === "control_request" &&
              m.request?.subtype === "can_use_tool"),
        );
        await log(`approval signal found: ${approvalSignal ? "YES" : "NO"}`);
        expect(approvalSignal).toBeDefined();

        expect(result.success).toBe(true);
        await log("success check: PASS");

        const resultCount = result.messages.filter(
          (m) => m.type === "result",
        ).length;
        await log(`result message count: ${resultCount}`);
        expect(resultCount).toBeGreaterThanOrEqual(1);

        const recoveryMessage = result.messages.find(
          (m) =>
            m.type === "recovery" && m.recovery_type === "approval_pending",
        );
        if (recoveryMessage) {
          await log(
            "Recovery message detected — lazy recovery worked correctly",
          );
          console.log(
            "Recovery message detected - lazy recovery worked correctly",
          );
          expect(result.errorSeen).toBe(true);
        } else {
          await log(
            "No recovery message seen — approval may have been handled before conflict (timing-dependent)",
          );
          console.log(
            "Note: No recovery message seen - approval may have been handled before conflict",
          );
        }

        await log("All assertions passed — test complete");
      } finally {
        // Keep the logger row intact so post-run inspection can see the full trace.
        if (loggerReady) await logger.flushLogs();
      }
    },
    320000,
  ); // 5+ minute timeout for slow CI runners
});
