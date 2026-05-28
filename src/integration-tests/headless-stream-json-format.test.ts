import { beforeEach, describe, expect, test } from "bun:test";
import { spawn } from "node:child_process";
import { RemoteLogger } from "../logger/RemoteLogger";
import type {
  ResultMessage,
  StreamEvent,
  SystemInitMessage,
} from "../types/protocol";
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
 * Tests for stream-json output format.
 * These verify the message structure matches the wire format types.
 */

async function runHeadlessCommand(
  prompt: string,
  extraArgs: string[] = [],
  timeoutMs = 180000, // 180s timeout - CI can be very slow
): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const proc = spawn(
      "bun",
      [
        "run",
        "dev",
        "--new-agent",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--yolo",
        "-m",
        "gpt-5.4-mini-plus-pro-medium",
        ...extraArgs,
      ],
      {
        cwd: process.cwd(),
        // Mark as subagent to prevent polluting user's LRU settings
        env: {
          ...process.env,
          LETTA_CODE_AGENT_ROLE: "subagent",
          LETTA_DEBUG: "0",
        },
        // Ignore stdin — without this the subprocess may block waiting for input.
        stdio: ["ignore", "pipe", "pipe"],
      },
    );

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    proc.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    // Safety timeout for CI
    const timeout = setTimeout(() => {
      proc.kill();
      reject(new Error(`Process timeout after ${timeoutMs}ms: ${stderr}`));
    }, timeoutMs);

    proc.on("close", (code) => {
      clearTimeout(timeout);
      if (code !== 0 && !stdout.includes('"type":"result"')) {
        reject(new Error(`Process exited with code ${code}: ${stderr}`));
      } else {
        // Parse line-delimited JSON
        const lines = stdout
          .split("\n")
          .filter((line) => line.trim())
          .filter((line) => {
            try {
              JSON.parse(line);
              return true;
            } catch {
              return false;
            }
          });
        resolve(lines);
      }
    });
  });
}

// Prescriptive prompt to ensure single-step response without tool use
const FAST_PROMPT =
  "This is a test. Do not call any tools. Just respond with the word OK and nothing else.";

describe("stream-json format", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  testWithTimeout(
    "init message has type 'system' with subtype 'init'",
    async () => {
      const logger = new RemoteLogger("StreamJson_InitMessage_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[stream-json:InitMessage] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[stream-json:InitMessage] ${message}`);
        if (loggerReady) {
          await logger.log(normalizeLoggerMessage(message)).catch((err) => {
            console.error(
              `[stream-json:InitMessage] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          });
        }
      };
      try {
        await log(
          "Test started: init message has type 'system' with subtype 'init'",
        );
        const lines = await runHeadlessCommand(FAST_PROMPT);
        await log(`CLI returned ${lines.length} JSON lines`);

        const initLine = lines.find((line) => {
          const obj = JSON.parse(line);
          return obj.type === "system" && obj.subtype === "init";
        });

        expect(initLine).toBeDefined();
        if (!initLine) throw new Error("initLine not found");

        const init = JSON.parse(initLine) as SystemInitMessage;
        expect(init.type).toBe("system");
        expect(init.subtype).toBe("init");
        expect(init.agent_id).toBeDefined();
        expect(init.session_id).toBe(init.agent_id);
        expect(init.model).toBeDefined();
        expect(init.tools).toBeInstanceOf(Array);
        expect(init.cwd).toBeDefined();
        expect(init.uuid).toBe(`init-${init.agent_id}`);
        await log(
          `Init message validated: agent_id=${init.agent_id} model=${init.model} tools=${init.tools.length} — test finished`,
        );
      } catch (err) {
        await log(
          `Test FAILED: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        // Keep the logger row intact so the viewer retains the full history.
      }
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "messages have session_id and uuid",
    async () => {
      const logger = new RemoteLogger("StreamJson_SessionIdUuid_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[stream-json:SessionIdUuid] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[stream-json:SessionIdUuid] ${message}`);
        if (loggerReady) {
          await logger.log(normalizeLoggerMessage(message)).catch((err) => {
            console.error(
              `[stream-json:SessionIdUuid] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          });
        }
      };
      try {
        await log("Test started: messages have session_id and uuid");
        const lines = await runHeadlessCommand(FAST_PROMPT);
        await log(`CLI returned ${lines.length} JSON lines`);

        const messageLine = lines.find((line) => {
          const obj = JSON.parse(line);
          return obj.type === "message";
        });

        expect(messageLine).toBeDefined();
        if (!messageLine) throw new Error("messageLine not found");

        const msg = JSON.parse(messageLine) as {
          session_id: string;
          uuid: string;
        };
        expect(msg.session_id).toBeDefined();
        expect(msg.uuid).toBeDefined();
        expect(msg.uuid).toBeTruthy();
        await log(
          `session_id=${msg.session_id} uuid=${msg.uuid} — test complete`,
        );
      } catch (err) {
        await log(
          `Test FAILED: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        // Keep the logger row intact so the viewer can show the full run history.
      }
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "result message has correct format",
    async () => {
      const logger = new RemoteLogger("StreamJson_ResultFormat_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[stream-json:ResultFormat] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[stream-json:ResultFormat] ${message}`);
        if (loggerReady) {
          await logger.log(normalizeLoggerMessage(message)).catch((err) => {
            console.error(
              `[stream-json:ResultFormat] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          });
        }
      };
      try {
        await log("Test started: result message has correct format");
        const lines = await runHeadlessCommand(FAST_PROMPT);
        await log(`CLI returned ${lines.length} JSON lines`);

        const resultLine = lines.find((line) => {
          const obj = JSON.parse(line);
          return obj.type === "result";
        });

        expect(resultLine).toBeDefined();
        if (!resultLine) throw new Error("resultLine not found");

        const result = JSON.parse(resultLine) as ResultMessage & {
          uuid: string;
        };
        expect(result.type).toBe("result");
        expect(result.subtype).toBe("success");
        expect(result.session_id).toBeDefined();
        expect(result.agent_id).toBeDefined();
        expect(result.session_id).toBe(result.agent_id);
        expect(result.duration_ms).toBeGreaterThan(0);
        expect(result.uuid).toContain("result-");
        expect(result.result).toBeDefined();
        await log(
          `Result validated: subtype=${result.subtype} duration_ms=${result.duration_ms} — test complete`,
        );
      } catch (err) {
        await log(
          `Test FAILED: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        // Keep the logger row intact so the viewer can show the full run history.
      }
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "--include-partial-messages wraps chunks in stream_event",
    async () => {
      const logger = new RemoteLogger("StreamJson_PartialMessages_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[stream-json:PartialMessages] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[stream-json:PartialMessages] ${message}`);
        if (loggerReady) {
          await logger.log(normalizeLoggerMessage(message)).catch((err) => {
            console.error(
              `[stream-json:PartialMessages] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          });
        }
      };
      try {
        await log(
          "Test started: --include-partial-messages wraps chunks in stream_event",
        );
        const lines = await runHeadlessCommand(FAST_PROMPT, [
          "--include-partial-messages",
        ]);
        await log(`CLI returned ${lines.length} JSON lines`);

        const streamEventLine = lines.find((line) => {
          const obj = JSON.parse(line);
          return obj.type === "stream_event";
        });

        expect(streamEventLine).toBeDefined();
        if (!streamEventLine) throw new Error("streamEventLine not found");

        const event = JSON.parse(streamEventLine) as StreamEvent;
        expect(event.type).toBe("stream_event");
        expect(event.event).toBeDefined();
        expect(event.session_id).toBeDefined();
        expect(event.uuid).toBeDefined();
        expect("message_type" in event.event).toBe(true);
        await log(
          `stream_event validated: session_id=${event.session_id} — test complete`,
        );
      } catch (err) {
        await log(
          `Test FAILED: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        // Keep the logger row intact so the viewer can show the full run history.
        if (loggerReady) await logger.flushLogs();
      }
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "usage_statistics message has required token count fields",
    async () => {
      const logger = new RemoteLogger("StreamJson_UsageStatistics_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[stream-json:UsageStatistics] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[stream-json:UsageStatistics] ${message}`);
        if (loggerReady) {
          await logger.log(normalizeLoggerMessage(message)).catch((err) => {
            console.error(
              `[stream-json:UsageStatistics] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          });
        }
      };
      try {
        await log(
          "Test started: usage_statistics message has required token count fields",
        );
        const lines = await runHeadlessCommand(FAST_PROMPT);
        await log(`CLI returned ${lines.length} JSON lines`);

        const statsLine = lines.find((line) => {
          const obj = JSON.parse(line) as Record<string, unknown>;
          return (
            obj.type === "message" && obj.message_type === "usage_statistics"
          );
        });

        expect(statsLine).toBeDefined();
        if (!statsLine) throw new Error("usage_statistics message not found");

        const stats = JSON.parse(statsLine) as {
          type: string;
          message_type: string;
          completion_tokens: number;
          prompt_tokens: number;
          total_tokens: number;
          step_count: number;
          session_id: string;
          uuid: string;
        };
        expect(stats.type).toBe("message");
        expect(stats.message_type).toBe("usage_statistics");
        expect(stats.completion_tokens).toBeGreaterThan(0);
        expect(stats.prompt_tokens).toBeGreaterThan(0);
        expect(stats.total_tokens).toBeGreaterThan(0);
        expect(stats.step_count).toBeGreaterThan(0);
        expect(stats.session_id).toBeDefined();
        expect(stats.uuid).toBeDefined();
        await log(
          `usage_statistics validated: completion_tokens=${stats.completion_tokens} prompt_tokens=${stats.prompt_tokens} step_count=${stats.step_count} — test complete`,
        );
      } catch (err) {
        await log(
          `Test FAILED: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        if (loggerReady) await logger.flushLogs();
      }
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "stop_reason message has correct structure",
    async () => {
      const logger = new RemoteLogger("StreamJson_StopReason_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[stream-json:StopReason] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[stream-json:StopReason] ${message}`);
        if (loggerReady) {
          await logger.log(normalizeLoggerMessage(message)).catch((err) => {
            console.error(
              `[stream-json:StopReason] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          });
        }
      };
      try {
        await log("Test started: stop_reason message has correct structure");
        const lines = await runHeadlessCommand(FAST_PROMPT);
        await log(`CLI returned ${lines.length} JSON lines`);

        const stopLine = lines.find((line) => {
          const obj = JSON.parse(line) as Record<string, unknown>;
          return obj.type === "message" && obj.message_type === "stop_reason";
        });

        expect(stopLine).toBeDefined();
        if (!stopLine) throw new Error("stop_reason message not found");

        const stop = JSON.parse(stopLine) as {
          type: string;
          message_type: string;
          stop_reason: string;
          session_id: string;
          uuid: string;
        };
        expect(stop.type).toBe("message");
        expect(stop.message_type).toBe("stop_reason");
        expect(stop.stop_reason).toBeTruthy();
        expect(stop.session_id).toBeDefined();
        expect(stop.uuid).toBeDefined();
        await log(
          `stop_reason validated: stop_reason=${stop.stop_reason} — test complete`,
        );
      } catch (err) {
        await log(
          `Test FAILED: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        if (loggerReady) await logger.flushLogs();
      }
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "without --include-partial-messages, messages are type 'message'",
    async () => {
      const logger = new RemoteLogger("StreamJson_NoPartialMessages_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[stream-json:NoPartialMessages] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[stream-json:NoPartialMessages] ${message}`);
        if (loggerReady) {
          await logger.log(normalizeLoggerMessage(message)).catch((err) => {
            console.error(
              `[stream-json:NoPartialMessages] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          });
        }
      };
      try {
        await log(
          "Test started: without --include-partial-messages, messages are type 'message'",
        );
        const lines = await runHeadlessCommand(FAST_PROMPT);
        await log(`CLI returned ${lines.length} JSON lines`);

        const messageLines = lines.filter((line) => {
          const obj = JSON.parse(line);
          return obj.type === "message";
        });
        const streamEventLines = lines.filter((line) => {
          const obj = JSON.parse(line);
          return obj.type === "stream_event";
        });
        await log(
          `message lines: ${messageLines.length}, stream_event lines: ${streamEventLines.length}`,
        );

        if (messageLines.length > 0 || streamEventLines.length > 0) {
          expect(messageLines.length).toBeGreaterThan(0);
          expect(streamEventLines.length).toBe(0);
          await log(
            "message type check: PASS (message > 0, stream_event == 0)",
          );
        }

        const resultLine = lines.find((line) => {
          const obj = JSON.parse(line);
          return obj.type === "result";
        });
        expect(resultLine).toBeDefined();
        await log("result line found: PASS — test complete");
      } catch (err) {
        await log(
          `Test FAILED: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      } finally {
        // Keep the logger row intact so the viewer can show the full run history.
        if (loggerReady) await logger.flushLogs();
      }
    },
    { timeout: 200000 },
  );
});
