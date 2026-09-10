import { describe, expect, test } from "bun:test";

import { readScannerIntakeStatus } from "../abstract/scanner-intake-status.js";

describe("readScannerIntakeStatus", () => {
  test("accepts a completed intake with its isolated conversation", () => {
    expect(
      readScannerIntakeStatus({
        ok: true,
        status: "PASS",
        conversation_id: "conv-window-123",
        dispatched_at: 1725900000.25,
      }),
    ).toEqual({
      ok: true,
      status: "pass",
      conversationId: "conv-window-123",
      dispatchedAt: 1725900000.25,
      terminal: true,
      error: null,
    });
  });

  test("never carries a shell-shaped conversation id", () => {
    const status = readScannerIntakeStatus({
      ok: true,
      status: "pass",
      conversation_id: "conv-ok;echo wrong",
    });
    expect(status.conversationId).toBeNull();
    expect(status.terminal).toBe(true);
  });

  test("recognizes every terminal intake outcome", () => {
    for (const status of [
      "complete",
      "pass",
      "corrected",
      "fail",
      "stalled",
      "awaiting_vendor_review",
      "needs_human_review",
    ]) {
      expect(readScannerIntakeStatus({ ok: true, status }).terminal).toBe(true);
    }
  });

  test("fails closed on malformed HTTP data", () => {
    expect(readScannerIntakeStatus(null).ok).toBe(false);
    expect(readScannerIntakeStatus({ ok: true }).ok).toBe(false);
  });

  test("drops a malformed dispatch generation", () => {
    const status = readScannerIntakeStatus({
      ok: true,
      status: "processing",
      dispatched_at: "yesterday",
    });
    expect(status.dispatchedAt).toBeNull();
  });
});
