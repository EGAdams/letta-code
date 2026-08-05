import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

describe("inactivity timeout cancellation wiring", () => {
  test("cancels the backend before drainStreamWithResume returns", () => {
    const streamPath = fileURLToPath(
      new URL("../../cli/helpers/stream.ts", import.meta.url),
    );
    const source = readFileSync(streamPath, "utf8");
    const start = source.indexOf(
      "if (result.inactivityTimedOut && streamRequestContext)",
    );
    const end = source.indexOf("// If the initial drain's catch block", start);
    const segment = source.slice(start, end);

    expect(start).toBeGreaterThan(-1);
    expect(end).toBeGreaterThan(start);
    expect(segment).toContain("await client.conversations.cancel(cancelId)");
    expect(segment).toContain("result.backendCancelSucceeded = true");
  });

  test("the TUI distinguishes watchdog timeout from a user interrupt", () => {
    const appPath = fileURLToPath(
      new URL("../../cli/App.tsx", import.meta.url),
    );
    const source = readFileSync(appPath, "utf8");
    const start = source.indexOf('if (stopReasonToHandle === "cancelled")');
    const end = source.indexOf("// Case 2: Requires approval", start);
    const segment = source.slice(start, end);

    expect(start).toBeGreaterThan(-1);
    expect(end).toBeGreaterThan(start);
    expect(segment).toContain("if (inactivityTimedOut)");
    // The wording itself lives in inactivityStopMessage, which is unit-tested
    // in stream-activity/inactivity-message.test.ts. What matters here is that
    // the TUI delegates to it and forwards which deadline actually fired —
    // hardcoding "90 seconds" here is what made the Mazda stop misleading.
    expect(segment).toContain("inactivityStopMessage(");
    expect(segment).toContain("inactivityReason");
    expect(segment).not.toContain("90 seconds");
  });
});
