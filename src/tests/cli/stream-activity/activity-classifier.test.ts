import { describe, expect, test } from "bun:test";
import { classifyStreamActivity } from "../../../cli/helpers/stream-activity";

describe("classifyStreamActivity", () => {
  test("the two ends of a tool call are distinguished", () => {
    // The gap between them is the tool executing — legitimate silence that
    // must not read as a dead stream, so they cannot collapse to one kind.
    expect(classifyStreamActivity("tool_call_message")).toBe("tool_started");
    expect(classifyStreamActivity("tool_return_message")).toBe("tool_finished");
  });

  test("model output is content, not tool progress", () => {
    expect(classifyStreamActivity("reasoning_message")).toBe("content");
    expect(classifyStreamActivity("assistant_message")).toBe("content");
    expect(classifyStreamActivity("hidden_reasoning_message")).toBe("content");
    expect(classifyStreamActivity("approval_request_message")).toBe("content");
  });

  test("a ping proves nothing — it is what the watchdog exists to catch", () => {
    expect(classifyStreamActivity("ping")).toBeNull();
  });

  test("bookkeeping chunks prove nothing", () => {
    expect(classifyStreamActivity("stop_reason")).toBeNull();
    expect(classifyStreamActivity("usage_statistics")).toBeNull();
  });

  test("unknown and missing types fail closed", () => {
    expect(classifyStreamActivity("something_new")).toBeNull();
    expect(classifyStreamActivity(undefined)).toBeNull();
    expect(classifyStreamActivity("")).toBeNull();
  });
});
