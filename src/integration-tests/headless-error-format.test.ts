import { beforeEach, describe, expect, test } from "bun:test";
import type {
  ErrorMessage,
  ResultMessage,
  ResultSubtype,
} from "../types/protocol";
import { RemoteLogger } from "../logger/RemoteLogger";
import { resetAllLoggers } from "./logger-helpers";

const TEST_TIMEOUT_MS = 30000;

const normalizeLoggerMessage = (message: string): string => {
  if (message.includes("ERROR")) return message;
  if (/\bFAIL(?:ED)?\b/.test(message)) return `ERROR: `;
  if (/\bPASS(?:ED)?\b/.test(message) || /test complete|test finished/i.test(message)) {
    return message.includes("finished") ? message : ` finished`;
  }
  return message;
};
const testWithTimeout = (name: string, fn: () => Promise<void> | void) =>
  test(name, fn, TEST_TIMEOUT_MS);

/**
 * Tests for error handling in headless mode.
 *
 * These tests document and verify the expected wire format for errors.
 * See GitHub issue #813 for background.
 *
 * Expected behavior:
 * 1. When an error occurs, ResultMessage.subtype should be "error" (not "success")
 * 2. ErrorMessage should contain detailed API error info when available
 * 3. Both one-shot and bidirectional modes should surface errors properly
 */

describe("headless error format types", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  testWithTimeout("ResultSubtype includes 'error' option", async () => {
    const logger = new RemoteLogger("ErrorFormat_ResultSubtype_2026");
    let loggerReady = false;
    try {
      await logger.init();
      loggerReady = true;
    } catch (err) {
      console.warn(`[error-format:ResultSubtype] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
    }
    const log = async (message: string) => {
      console.log(`[error-format:ResultSubtype] ${message}`);
      if (loggerReady) {
        try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
          console.error(`[error-format:ResultSubtype] log failed: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    };

    await log("Test started: ResultSubtype includes 'error' option");
    const errorSubtype: ResultSubtype = "error";
    expect(errorSubtype).toBe("error");
    await log("errorSubtype === 'error': PASS");

    const successSubtype: ResultSubtype = "success";
    expect(successSubtype).toBe("success");
    await log("successSubtype === 'success': PASS");

    const interruptedSubtype: ResultSubtype = "interrupted";
    expect(interruptedSubtype).toBe("interrupted");
    await log("interruptedSubtype === 'interrupted': PASS — test complete");
  });

  testWithTimeout("ResultMessage type supports stop_reason field", async () => {
    const logger = new RemoteLogger("ErrorFormat_StopReason_2026");
    let loggerReady = false;
    try {
      await logger.init();
      loggerReady = true;
    } catch (err) {
      console.warn(`[error-format:StopReason] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
    }
    const log = async (message: string) => {
      console.log(`[error-format:StopReason] ${message}`);
      if (loggerReady) {
        try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
          console.error(`[error-format:StopReason] log failed: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    };

    await log("Test started: ResultMessage type supports stop_reason field");
    const errorResult: ResultMessage = {
      type: "result",
      subtype: "error",
      session_id: "test-session",
      uuid: "test-uuid",
      agent_id: "agent-123",
      conversation_id: "conv-123",
      duration_ms: 1000,
      duration_api_ms: 500,
      num_turns: 1,
      result: null,
      run_ids: ["run-123"],
      usage: null,
      stop_reason: "error",
    };
    expect(errorResult.subtype).toBe("error");
    await log("errorResult.subtype === 'error': PASS");
    expect(errorResult.stop_reason).toBe("error");
    await log("errorResult.stop_reason === 'error': PASS — test complete");
  });

  testWithTimeout("ErrorMessage type supports api_error field", async () => {
    const logger = new RemoteLogger("ErrorFormat_ApiError_2026");
    let loggerReady = false;
    try {
      await logger.init();
      loggerReady = true;
    } catch (err) {
      console.warn(`[error-format:ApiError] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
    }
    const log = async (message: string) => {
      console.log(`[error-format:ApiError] ${message}`);
      if (loggerReady) {
        try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
          console.error(`[error-format:ApiError] log failed: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    };

    await log("Test started: ErrorMessage type supports api_error field");
    const errorMsg: ErrorMessage = {
      type: "error",
      message: "CONFLICT: Another request is being processed",
      stop_reason: "error",
      session_id: "test-session",
      uuid: "test-uuid",
      run_id: "run-123",
      api_error: {
        message_type: "error_message",
        message: "CONFLICT: Another request is being processed",
        error_type: "internal_error",
        detail:
          "Cannot send a new message: Another request is currently being processed for this conversation.",
        run_id: "run-123",
      },
    };
    expect(errorMsg.type).toBe("error");
    await log("errorMsg.type === 'error': PASS");
    expect(errorMsg.api_error).toBeDefined();
    await log("errorMsg.api_error defined: PASS");
    expect(errorMsg.api_error?.detail).toContain("Another request");
    await log("api_error.detail contains 'Another request': PASS — test complete");
  });
});

describe("headless error format expectations", () => {
  /**
   * These tests document the EXPECTED behavior for error handling.
   * They verify the wire format contracts that the SDK depends on.
   */

  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  testWithTimeout("error result should have subtype 'error', not 'success'", async () => {
    const logger = new RemoteLogger("ErrorFormat_ErrorSubtypeCheck_2026");
    let loggerReady = false;
    try {
      await logger.init();
      loggerReady = true;
    } catch (err) {
      console.warn(`[error-format:ErrorSubtype] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
    }
    const log = async (message: string) => {
      console.log(`[error-format:ErrorSubtype] ${message}`);
      if (loggerReady) {
        try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
          console.error(`[error-format:ErrorSubtype] log failed: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    };

    await log("Test started: error result should have subtype 'error', not 'success'");
    const mockErrorResult: ResultMessage = {
      type: "result",
      subtype: "error",
      session_id: "test",
      uuid: "test",
      agent_id: "agent-123",
      conversation_id: "conv-123",
      duration_ms: 1000,
      duration_api_ms: 500,
      num_turns: 1,
      result: null,
      run_ids: [],
      usage: null,
      stop_reason: "error",
    };
    const sdkSuccess = mockErrorResult.subtype === "success";
    expect(sdkSuccess).toBe(false);
    await log(`sdkSuccess === false (subtype='${mockErrorResult.subtype}'): PASS — test complete`);
  });

  testWithTimeout("409 conflict error should include detail in message", async () => {
    const logger = new RemoteLogger("ErrorFormat_ConflictDetail_2026");
    let loggerReady = false;
    try {
      await logger.init();
      loggerReady = true;
    } catch (err) {
      console.warn(`[error-format:ConflictDetail] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
    }
    const log = async (message: string) => {
      console.log(`[error-format:ConflictDetail] ${message}`);
      if (loggerReady) {
        try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
          console.error(`[error-format:ConflictDetail] log failed: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    };

    await log("Test started: 409 conflict error should include detail in message");
    const conflictDetail =
      "CONFLICT: Cannot send a new message: Another request is currently being processed for this conversation.";
    const mockError: ErrorMessage = {
      type: "error",
      message: conflictDetail,
      stop_reason: "error",
      session_id: "test",
      uuid: "test",
      run_id: "run-123",
    };
    expect(mockError.message).toContain("CONFLICT");
    await log("message contains 'CONFLICT': PASS");
    expect(mockError.message).toContain("Another request");
    await log("message contains 'Another request': PASS — test complete");
  });

  testWithTimeout("approval pending error should include detail", async () => {
    const logger = new RemoteLogger("ErrorFormat_ApprovalDetail_2026");
    let loggerReady = false;
    try {
      await logger.init();
      loggerReady = true;
    } catch (err) {
      console.warn(`[error-format:ApprovalDetail] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
    }
    const log = async (message: string) => {
      console.log(`[error-format:ApprovalDetail] ${message}`);
      if (loggerReady) {
        try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
          console.error(`[error-format:ApprovalDetail] log failed: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    };

    await log("Test started: approval pending error should include detail");
    const approvalDetail =
      "CONFLICT: Cannot send a new message: The agent is waiting for approval on a tool call.";
    const mockError: ErrorMessage = {
      type: "error",
      message: approvalDetail,
      stop_reason: "error",
      session_id: "test",
      uuid: "test",
    };
    expect(mockError.message).toContain("waiting for approval");
    await log("message contains 'waiting for approval': PASS — test complete");
  });
});

/**
 * Note for SDK team:
 *
 * The SDK (letta-code-sdk) transforms ResultMessage as follows:
 *
 *   success: msg.subtype === "success"
 *   error: msg.subtype !== "success" ? msg.subtype : undefined
 *
 * With this fix:
 * - Error results will have subtype: "error", so success will be false
 * - The error field will be "error" (the subtype string)
 *
 * For more detailed error info, SDK could be updated to:
 * 1. Parse ErrorMessage events (currently ignored)
 * 2. Use stop_reason from ResultMessage for specific error types
 */
