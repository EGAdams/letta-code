import { describe, expect, test } from "bun:test";
import {
  ClaudeSdkActivityController,
  eventText,
  statusText,
} from "../implementation/claude-sdk-activity-controller.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(payload) {
  const doc = new FakeDocument();
  for (const id of [
    "claude-sdk-live-status",
    "claude-sdk-live-progress",
    "claude-sdk-thoughts",
    "claude-sdk-tool-calls",
    "claude-sdk-messages",
  ]) {
    const el = doc.createElement("div");
    el.id = id;
  }
  const controller = new ClaudeSdkActivityController({
    doc,
    http: { getJSON: async () => payload },
    setInterval: () => 1,
    clearInterval: () => {},
  });
  return { doc, controller };
}

describe("ClaudeSdkActivityController", () => {
  test("renders running state into three separate scrolling dialogs", async () => {
    const { doc, controller } = setup({
      ok: true,
      current_run: {
        status: "running",
        model: "sonnet",
        working_dir: "/work",
      },
      events: [
        { seq: 1, timestamp: 1, category: "thoughts", text: "plan" },
        {
          seq: 2,
          timestamp: 2,
          category: "tool_calls",
          text: "Read",
          tool: "Read",
          input: { file_path: "a.txt" },
        },
        { seq: 3, timestamp: 3, category: "messages", text: "done" },
      ],
    });

    await controller.poll();

    expect(doc.getElementById("claude-sdk-live-status").textContent).toContain(
      "Running sonnet in /work",
    );
    expect(
      doc
        .getElementById("claude-sdk-live-progress")
        .classList.contains("is-running"),
    ).toBe(true);
    expect(
      doc.getElementById("claude-sdk-thoughts").children[0].children[1]
        .textContent,
    ).toBe("plan");
    expect(
      doc.getElementById("claude-sdk-tool-calls").children[0].children[1]
        .textContent,
    ).toContain('"file_path": "a.txt"');
    expect(
      doc.getElementById("claude-sdk-messages").children[0].children[1]
        .textContent,
    ).toBe("done");
  });

  test("fails visibly when the executor feed is unavailable", async () => {
    const { doc, controller } = setup({ ok: false, error: "offline" });

    await controller.poll();

    expect(doc.getElementById("claude-sdk-live-status").textContent).toContain(
      "offline",
    );
    expect(
      doc
        .getElementById("claude-sdk-live-status")
        .classList.contains("is-error"),
    ).toBe(true);
  });
});

test("activity formatting keeps tool input and terminal state explicit", () => {
  expect(
    eventText({
      category: "tool_calls",
      tool: "Bash",
      input: { command: "pwd" },
    }),
  ).toContain('"command": "pwd"');
  expect(statusText({ status: "cancelled", working_dir: "/repo" })).toBe(
    "Cancelled in /repo.",
  );
});
