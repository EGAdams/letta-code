import { describe, expect, test } from "bun:test";
import { inactivityStopMessage } from "../../../cli/helpers/stream-activity";

describe("inactivityStopMessage", () => {
  test("a silent stream names the short deadline", () => {
    const msg = inactivityStopMessage("no_content", true);
    expect(msg).toContain("90 seconds without a response from the model");
    expect(msg).toContain("backend run was cancelled");
  });

  test("a planning loop names the long deadline, not 90 seconds", () => {
    const msg = inactivityStopMessage("no_tool_progress", true);
    expect(msg).toContain("10 minutes of reasoning without running a tool");
    expect(msg).not.toContain("90 seconds");
  });

  test("an unconfirmed cancel tells the user how to recover", () => {
    const msg = inactivityStopMessage("no_content", false);
    expect(msg).toContain("could not be confirmed");
    expect(msg).toContain("letta --new");
  });

  test("the wording follows the thresholds that actually fired", () => {
    const msg = inactivityStopMessage("no_content", true, {
      noContentMs: 45_000,
      noToolProgressMs: 120_000,
      pollIntervalMs: 5_000,
    });
    expect(msg).toContain("45 seconds");
  });
});
