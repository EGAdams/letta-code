import { beforeEach, describe, expect, test } from "bun:test";
import { spawn } from "node:child_process";
import { RemoteLogger } from "../logger/RemoteLogger";
import type {
  ControlResponse,
  ErrorMessage,
  ResultMessage,
  StreamEvent,
  SystemInitMessage,
  WireMessage,
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
 * Tests for --input-format stream-json bidirectional communication.
 * These verify the CLI's wire format for bidirectional communication.
 */

// Prescriptive prompt to ensure single-step response without tool use
const FAST_PROMPT =
  "This is a test. Do not call any tools. Just respond with the word OK and nothing else.";

/**
 * Helper to run bidirectional commands with stdin input.
 * Event-driven: waits for init message before sending input, waits for result before closing.
 */
async function runBidirectional(
  inputs: string[],
  extraArgs: string[] = [],
  timeoutMs = 180000, // 180s timeout - CI can be very slow
): Promise<object[]> {
  return new Promise((resolve, reject) => {
    const args = [
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
      "--yolo",
      ...extraArgs,
    ];
    console.log(`[runBidirectional] spawning: bun ${args.join(" ")}`);
    console.log(
      `[runBidirectional] LETTA_BASE_URL=${process.env.LETTA_BASE_URL ?? "(unset)"}`,
    );
    const proc = spawn("bun", args, {
      cwd: process.cwd(),
      // Mark as subagent to prevent polluting user's LRU settings
      env: { ...process.env, LETTA_CODE_AGENT_ROLE: "subagent" },
    });
    console.log(`[runBidirectional] process pid=${proc.pid}`);

    const objects: object[] = [];
    let buffer = "";
    let inputIndex = 0;
    let initReceived = false;
    let closing = false;

    // Count expected responses based on input types
    const inputTypes = inputs.map((i) => {
      try {
        const parsed = JSON.parse(i);
        return parsed.type;
      } catch {
        return "invalid"; // Invalid JSON
      }
    });
    const expectedUserResults = inputTypes.filter((t) => t === "user").length;
    const expectedControlResponses = inputTypes.filter(
      (t) => t === "control_request",
    ).length;
    const hasInvalidInput = inputTypes.includes("invalid");

    let userResultsReceived = 0;
    let controlResponsesReceived = 0;

    const maybeClose = () => {
      if (closing) return;

      const allUserResultsDone =
        expectedUserResults === 0 || userResultsReceived >= expectedUserResults;
      const allControlResponsesDone =
        expectedControlResponses === 0 ||
        controlResponsesReceived >= expectedControlResponses;
      const allInputsSent = inputIndex >= inputs.length;

      console.log(
        `[runBidirectional] maybeClose check: allInputsSent=${allInputsSent} userResults=${userResultsReceived}/${expectedUserResults} controlResponses=${controlResponsesReceived}/${expectedControlResponses}`,
      );

      if (allInputsSent && allUserResultsDone && allControlResponsesDone) {
        closing = true;
        console.log("[runBidirectional] all done — closing stdin in 500ms");
        setTimeout(() => proc.stdin?.end(), 500);
      }
    };

    const processLine = (line: string) => {
      if (!line.trim()) return;
      try {
        const obj = JSON.parse(line) as Record<string, unknown>;
        objects.push(obj);
        console.log(
          `[runBidirectional] stdout JSON: type=${obj.type} subtype=${obj.subtype ?? "-"} objects_so_far=${objects.length}`,
        );

        if (obj.type === "system" && obj.subtype === "init" && !initReceived) {
          initReceived = true;
          console.log("[runBidirectional] init received — sending first input");
          sendNextInput();
        }

        if (obj.type === "control_response") {
          controlResponsesReceived++;
          console.log(
            `[runBidirectional] control_response #${controlResponsesReceived} received`,
          );
          maybeClose();
        }

        if (obj.type === "result") {
          userResultsReceived++;
          console.log(
            `[runBidirectional] result #${userResultsReceived} received`,
          );
          if (inputIndex < inputs.length) {
            setTimeout(sendNextInput, 200);
          }
          maybeClose();
        }

        if (obj.type === "error" && hasInvalidInput) {
          console.log(
            "[runBidirectional] error received with invalid input — closing stdin",
          );
          closing = true;
          setTimeout(() => proc.stdin?.end(), 500);
        }
      } catch {
        console.log(
          `[runBidirectional] stdout non-JSON line: ${line.slice(0, 120)}`,
        );
      }
    };

    const sendNextInput = () => {
      if (inputIndex < inputs.length) {
        const payload = inputs[inputIndex];
        if (payload === undefined) return;
        console.log(
          `[runBidirectional] sending input[${inputIndex}]: ${payload.slice(0, 120)}`,
        );
        proc.stdin?.write(`${payload}\n`);
        inputIndex++;
      }
    };

    proc.stdout?.on("data", (data: Buffer) => {
      const chunk = data.toString();
      console.log(
        `[runBidirectional] stdout chunk (${chunk.length} bytes): ${chunk.slice(0, 200).replace(/\n/g, "\\n")}`,
      );
      buffer += chunk;
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        processLine(line);
      }
    });

    let stderr = "";
    proc.stderr?.on("data", (data: Buffer) => {
      const chunk = data.toString();
      stderr += chunk;
      console.error(
        `[runBidirectional] STDERR: ${chunk.slice(0, 300).replace(/\n/g, " | ")}`,
      );
    });

    proc.on("close", (code) => {
      console.log(
        `[runBidirectional] process closed: code=${code} objects=${objects.length} initReceived=${initReceived}`,
      );
      if (buffer.trim()) {
        processLine(buffer);
      }

      const gotExpectedResults =
        userResultsReceived >= expectedUserResults &&
        controlResponsesReceived >= expectedControlResponses;

      if (objects.length === 0 && code !== 0) {
        reject(
          new Error(
            `Process exited with code ${code}, no output received. stderr: ${stderr}`,
          ),
        );
      } else if (!gotExpectedResults && code !== 0) {
        reject(
          new Error(
            `Process exited with code ${code} before all results received. ` +
              `Got ${userResultsReceived}/${expectedUserResults} user results, ` +
              `${controlResponsesReceived}/${expectedControlResponses} control responses. ` +
              `inputIndex: ${inputIndex}, initReceived: ${initReceived}. stderr: ${stderr}`,
          ),
        );
      } else {
        resolve(objects);
      }
    });

    const timeout = setTimeout(() => {
      console.error(
        `[runBidirectional] TIMEOUT after ${timeoutMs}ms — killing pid=${proc.pid}. ` +
          `objects=${objects.length} initReceived=${initReceived} ` +
          `userResults=${userResultsReceived}/${expectedUserResults} ` +
          `controlResponses=${controlResponsesReceived}/${expectedControlResponses} ` +
          `stderrTail=${stderr.slice(-500)}`,
      );
      proc.kill();
      reject(
        new Error(
          `Timeout after ${timeoutMs}ms. Received ${objects.length} objects, init: ${initReceived}, userResults: ${userResultsReceived}/${expectedUserResults}, controlResponses: ${controlResponsesReceived}/${expectedControlResponses}`,
        ),
      );
    }, timeoutMs);

    proc.on("close", () => clearTimeout(timeout));
  });
}

async function runBidirectionalWithRetry(
  inputs: string[],
  extraArgs: string[] = [],
  timeoutMs = 180000,
  retryOnTimeouts = 1,
): Promise<object[]> {
  let attempt = 0;
  while (true) {
    try {
      return await runBidirectional(inputs, extraArgs, timeoutMs);
    } catch (error) {
      const isTimeoutError =
        error instanceof Error && error.message.includes("Timeout after");
      if (!isTimeoutError || attempt >= retryOnTimeouts) {
        throw error;
      }
      attempt += 1;
      console.warn(
        `[headless-input-format] retrying after timeout (${attempt}/${retryOnTimeouts})`,
      );
    }
  }
}

describe("input-format stream-json", () => {
  beforeEach(async () => {
    console.log(
      "[beforeEach] Resetting all loggers via americansjewelry.com …",
    );
    const t0 = Date.now();
    await resetAllLoggers();
    console.log(
      `[beforeEach] resetAllLoggers complete in ${Date.now() - t0}ms`,
    );
  }, 30000);

  testWithTimeout(
    "initialize control request returns session info",
    async () => {
      const logger = new RemoteLogger("HeadlessInput_InitControl_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[headless-input:InitControl] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[headless-input:InitControl] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[headless-input:InitControl] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      await log(
        "Test started: initialize control request returns session info",
      );
      const objects = (await runBidirectional([
        JSON.stringify({
          type: "control_request",
          request_id: "init_1",
          request: { subtype: "initialize" },
        }),
      ])) as WireMessage[];
      await log(`CLI returned ${objects.length} objects`);

      const initEvent = objects.find(
        (o): o is SystemInitMessage =>
          o.type === "system" && "subtype" in o && o.subtype === "init",
      );
      expect(initEvent).toBeDefined();
      expect(initEvent?.agent_id).toBeDefined();
      expect(initEvent?.session_id).toBeDefined();
      expect(initEvent?.model).toBeDefined();
      expect(initEvent?.tools).toBeInstanceOf(Array);
      await log(
        `init event: agent_id=${initEvent?.agent_id} model=${initEvent?.model} tools=${initEvent?.tools?.length}`,
      );

      const controlResponse = objects.find(
        (o): o is ControlResponse => o.type === "control_response",
      );
      expect(controlResponse).toBeDefined();
      expect(controlResponse?.response.subtype).toBe("success");
      expect(controlResponse?.response.request_id).toBe("init_1");
      if (controlResponse?.response.subtype === "success") {
        const initResponse = controlResponse.response.response as
          | { agent_id?: string }
          | undefined;
        expect(initResponse?.agent_id).toBeDefined();
        await log(
          `control_response agent_id=${initResponse?.agent_id}: PASS — test complete`,
        );
      }
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "user message returns assistant response and result",
    async () => {
      const logger = new RemoteLogger("HeadlessInput_UserMessage_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[headless-input:UserMessage] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[headless-input:UserMessage] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[headless-input:UserMessage] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      await log(
        "Test started: user message returns assistant response and result",
      );
      await log(`Prompt: ${FAST_PROMPT}`);
      const objects = (await runBidirectional([
        JSON.stringify({
          type: "user",
          message: { role: "user", content: FAST_PROMPT },
        }),
      ])) as WireMessage[];
      await log(`CLI returned ${objects.length} objects`);

      const initEvent = objects.find(
        (o): o is SystemInitMessage =>
          o.type === "system" && "subtype" in o && o.subtype === "init",
      );
      expect(initEvent).toBeDefined();
      await log(`init event found: ${initEvent ? "YES" : "NO"}`);

      const messageEvents = objects.filter(
        (o): o is WireMessage & { type: "message" } => o.type === "message",
      );
      expect(messageEvents.length).toBeGreaterThan(0);
      await log(`message events: ${messageEvents.length}`);

      for (const msg of messageEvents) {
        expect(msg.session_id).toBeDefined();
      }

      const contentMessages = messageEvents.filter(
        (m) =>
          "message_type" in m &&
          (m.message_type === "reasoning_message" ||
            m.message_type === "assistant_message"),
      );
      for (const msg of contentMessages) {
        expect(msg.uuid).toBeDefined();
      }
      await log(`content messages with uuid: ${contentMessages.length}`);

      const result = objects.find(
        (o): o is ResultMessage => o.type === "result",
      );
      expect(result).toBeDefined();
      expect(result?.subtype).toBe("success");
      expect(result?.session_id).toBeDefined();
      expect(result?.agent_id).toBeDefined();
      expect(result?.duration_ms).toBeGreaterThan(0);
      await log(
        `result: subtype=${result?.subtype} duration_ms=${result?.duration_ms} — test complete`,
      );
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "multi-turn conversation maintains context",
    async () => {
      const logger = new RemoteLogger("HeadlessInput_MultiTurn_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[headless-input:MultiTurn] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[headless-input:MultiTurn] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[headless-input:MultiTurn] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      await log("Test started: multi-turn conversation maintains context");
      await log(
        "Sending 2 sequential messages: 'Say hello' then 'Say goodbye'",
      );
      const objects = (await runBidirectionalWithRetry(
        [
          JSON.stringify({
            type: "user",
            message: { role: "user", content: "Say hello" },
          }),
          JSON.stringify({
            type: "user",
            message: { role: "user", content: "Say goodbye" },
          }),
        ],
        [],
        300000,
        1,
      )) as WireMessage[];
      await log(`CLI returned ${objects.length} objects`);

      const results = objects.filter(
        (o): o is ResultMessage => o.type === "result",
      );
      await log(`result messages: ${results.length}`);
      expect(results.length).toBeGreaterThanOrEqual(2);

      for (const result of results) {
        expect(result.subtype).toBe("success");
        expect(result.session_id).toBeDefined();
        expect(result.agent_id).toBeDefined();
      }

      const firstResult = results[0];
      const lastResult = results[results.length - 1];
      expect(firstResult).toBeDefined();
      expect(lastResult).toBeDefined();
      if (firstResult && lastResult) {
        expect(firstResult.session_id).toBe(lastResult.session_id);
        await log(
          `session_id consistent across turns: ${firstResult.session_id} — test complete`,
        );
      }
    },
    { timeout: 320000 },
  );

  testWithTimeout(
    "interrupt control request is acknowledged",
    async () => {
      const logger = new RemoteLogger("HeadlessInput_Interrupt_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[headless-input:Interrupt] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[headless-input:Interrupt] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[headless-input:Interrupt] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      await log("Test started: interrupt control request is acknowledged");
      const objects = (await runBidirectional([
        JSON.stringify({
          type: "control_request",
          request_id: "int_1",
          request: { subtype: "interrupt" },
        }),
      ])) as WireMessage[];
      await log(`CLI returned ${objects.length} objects`);

      const controlResponse = objects.find(
        (o): o is ControlResponse =>
          o.type === "control_response" && o.response?.request_id === "int_1",
      );
      expect(controlResponse).toBeDefined();
      expect(controlResponse?.response.subtype).toBe("success");
      await log(
        `interrupt control_response subtype=${controlResponse?.response.subtype}: PASS — test complete`,
      );
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "recover_pending_approvals returns structured recovery payload",
    async () => {
      const logger = new RemoteLogger("HeadlessInput_RecoverApprovals_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[headless-input:RecoverApprovals] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[headless-input:RecoverApprovals] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[headless-input:RecoverApprovals] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      await log(
        "Test started: recover_pending_approvals returns structured recovery payload",
      );
      const objects = (await runBidirectional([
        JSON.stringify({
          type: "control_request",
          request_id: "recover_1",
          request: { subtype: "recover_pending_approvals" },
        }),
      ])) as WireMessage[];
      await log(`CLI returned ${objects.length} objects`);

      const controlResponse = objects.find(
        (o): o is ControlResponse =>
          o.type === "control_response" &&
          o.response?.request_id === "recover_1",
      );
      expect(controlResponse).toBeDefined();
      expect(controlResponse?.response.subtype).toBe("success");

      if (controlResponse?.response.subtype === "success") {
        const recovery = controlResponse.response.response as
          | {
              recovered?: boolean;
              pending_approval?: boolean;
              approvals_processed?: number;
            }
          | undefined;
        expect(recovery?.recovered).toBe(true);
        expect(recovery?.pending_approval).toBe(false);
        expect(recovery?.approvals_processed).toBe(0);
        await log(
          `recovery payload: recovered=${recovery?.recovered} pending_approval=${recovery?.pending_approval} approvals_processed=${recovery?.approvals_processed} — test complete`,
        );
      }
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "recover_pending_approvals agent mismatch returns error response",
    async () => {
      const logger = new RemoteLogger("HeadlessInput_RecoverMismatch_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[headless-input:RecoverMismatch] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[headless-input:RecoverMismatch] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[headless-input:RecoverMismatch] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      await log(
        "Test started: recover_pending_approvals agent mismatch returns error response",
      );
      await log("Sending mismatched agent_id: 'agent-mismatch'");
      const objects = (await runBidirectional([
        JSON.stringify({
          type: "control_request",
          request_id: "recover_mismatch_1",
          request: {
            subtype: "recover_pending_approvals",
            agent_id: "agent-mismatch",
          },
        }),
      ])) as WireMessage[];
      await log(`CLI returned ${objects.length} objects`);

      const controlResponse = objects.find(
        (o): o is ControlResponse =>
          o.type === "control_response" &&
          o.response?.request_id === "recover_mismatch_1",
      );
      expect(controlResponse).toBeDefined();
      expect(controlResponse?.response.subtype).toBe("error");

      if (controlResponse?.response.subtype === "error") {
        expect(controlResponse.response.error).toContain(
          "recover_pending_approvals agent mismatch",
        );
        await log(
          `error message contains 'recover_pending_approvals agent mismatch': PASS — test complete`,
        );
      }
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "--include-partial-messages emits stream_event in bidirectional mode",
    async () => {
      const logger = new RemoteLogger("HeadlessInput_PartialMessages_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[headless-input:PartialMessages] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[headless-input:PartialMessages] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[headless-input:PartialMessages] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      await log(
        "Test started: --include-partial-messages emits stream_event in bidirectional mode",
      );
      const objects = (await runBidirectional(
        [
          JSON.stringify({
            type: "user",
            message: { role: "user", content: FAST_PROMPT },
          }),
        ],
        ["--include-partial-messages"],
      )) as WireMessage[];
      await log(`CLI returned ${objects.length} objects`);

      const streamEvents = objects.filter(
        (o): o is StreamEvent => o.type === "stream_event",
      );
      await log(`stream_event count: ${streamEvents.length}`);
      expect(streamEvents.length).toBeGreaterThan(0);

      for (const event of streamEvents) {
        expect(event.event).toBeDefined();
        expect(event.session_id).toBeDefined();
      }

      const contentEvents = streamEvents.filter(
        (e) =>
          "message_type" in e.event &&
          (e.event.message_type === "reasoning_message" ||
            e.event.message_type === "assistant_message"),
      );
      for (const event of contentEvents) {
        expect(event.uuid).toBeDefined();
      }
      await log(`content stream_events with uuid: ${contentEvents.length}`);

      const result = objects.find(
        (o): o is ResultMessage => o.type === "result",
      );
      expect(result).toBeDefined();
      expect(result?.subtype).toBe("success");
      await log(`result subtype=${result?.subtype}: PASS — test complete`);
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "unknown control request returns error",
    async () => {
      const logger = new RemoteLogger("HeadlessInput_UnknownControl_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[headless-input:UnknownControl] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[headless-input:UnknownControl] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[headless-input:UnknownControl] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      await log("Test started: unknown control request returns error");
      try {
        await log("Sending control_request with subtype 'unknown_subtype'");
        const objects = (await runBidirectionalWithRetry([
          JSON.stringify({
            type: "control_request",
            request_id: "unknown_1",
            request: { subtype: "unknown_subtype" },
          }),
        ])) as WireMessage[];
        await log(`CLI returned ${objects.length} objects`);

        const controlResponse = objects.find(
          (o): o is ControlResponse =>
            o.type === "control_response" &&
            o.response?.request_id === "unknown_1",
        );
        expect(controlResponse).toBeDefined();
        expect(controlResponse?.response.subtype).toBe("error");
        await log(
          `control_response for unknown subtype: subtype=${controlResponse?.response.subtype} — test complete`,
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        await log(`ERROR: unknown control request test failed: ${msg}`);
        throw err;
      }
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "invalid JSON input returns error message",
    async () => {
      const logger = new RemoteLogger("HeadlessInput_InvalidJson_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[headless-input:InvalidJson] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[headless-input:InvalidJson] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[headless-input:InvalidJson] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      await log("Test started: invalid JSON input returns error message");
      await log("Sending raw string 'not valid json'");
      const objects = (await runBidirectional([
        "not valid json",
      ])) as WireMessage[];
      await log(`CLI returned ${objects.length} objects`);

      const errorMsg = objects.find(
        (o): o is ErrorMessage => o.type === "error",
      );
      expect(errorMsg).toBeDefined();
      expect(errorMsg?.message).toContain("Invalid JSON");
      await log(
        `error message: '${errorMsg?.message?.slice(0, 80)}' — test complete`,
      );
    },
    { timeout: 200000 },
  );

  testWithTimeout(
    "Task tool with explore subagent works",
    async () => {
      const logger = new RemoteLogger("HeadlessInput_TaskTool_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[headless-input:TaskTool] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[headless-input:TaskTool] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[headless-input:TaskTool] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      await log("Test started: Task tool with explore subagent works");
      await log(
        "Sending prompt requiring Task tool with subagent_type='explore'",
      );
      const objects = (await runBidirectional(
        [
          JSON.stringify({
            type: "user",
            message: {
              role: "user",
              content:
                "You MUST use the Task tool with subagent_type='explore' to find TypeScript files (*.ts) in the src directory. " +
                "Return only the subagent's report, nothing else.",
            },
          }),
        ],
        [],
        420000,
      )) as WireMessage[];
      await log(`CLI returned ${objects.length} objects`);

      const result = objects.find(
        (o): o is ResultMessage => o.type === "result",
      );
      expect(result).toBeDefined();
      expect(result?.subtype).toBe("success");
      await log(`result subtype=${result?.subtype}: PASS`);

      const autoApprovals = objects.filter((o) => o.type === "auto_approval");
      const approvalSignals = objects.filter((o) => {
        const messageType = (o as { message_type?: string }).message_type;
        return (
          o.type === "approval_requested" ||
          o.type === "approval_received" ||
          messageType === "approval_request_message"
        );
      });
      await log(
        `approval telemetry: auto_approval=${autoApprovals.length} other_signals=${approvalSignals.length}`,
      );
      expect(autoApprovals.length + approvalSignals.length).toBeGreaterThan(0);
      await log("approval telemetry present: PASS — test complete");
    },
    { timeout: 450000 },
  );
});
