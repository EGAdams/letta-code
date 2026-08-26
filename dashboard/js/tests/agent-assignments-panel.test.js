import { describe, expect, test } from "bun:test";
import { AgentAssignmentsController } from "../implementation/agent-assignments-panel.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(rows) {
  const doc = new FakeDocument();
  const container = doc.createElement("div");
  const http = { getJSON: async () => rows };
  const controller = new AgentAssignmentsController({
    http,
    el: (tag, props = {}) => Object.assign(doc.createElement(tag), props),
    buildModelSelect: () => doc.createElement("select"),
    container,
    setInterval: () => 1,
    clearInterval: () => {},
  });
  return { container, controller };
}

describe("AgentAssignmentsController tool rows", () => {
  test("renders run_claude_code_sdk as a token assignment with account selector", async () => {
    const { container, controller } = setup([
      {
        id: "tool-run-claude-code-sdk",
        name: "run_claude_code_sdk",
        model: "Claude Code SDK",
        assignment_kind: "tool",
        token_status: "up",
        token_status_detail: "",
      },
    ]);

    await controller.poll();

    const row = container.querySelector("tbody").children[0];
    expect(row.children[0].textContent).toBe("run_claude_code_sdk");
    expect(row.children[1].textContent).toBe("Claude Code SDK");
    expect(row.children[2].children[1].textContent).toBe("");
    expect(row.children[2].children[1].classList.contains("is-up")).toBe(true);
    expect(row.querySelector("select")).not.toBe(null);
  });

  test("renders an expired SDK token red", async () => {
    const { container, controller } = setup([
      {
        id: "tool-run-claude-code-sdk",
        name: "run_claude_code_sdk",
        model: "Claude Code SDK",
        assignment_kind: "tool",
        token_status: "down",
        token_status_detail:
          "OAuth token expired — run_claude_code_sdk will fail",
      },
    ]);

    await controller.poll();

    const token =
      container.querySelector("tbody").children[0].children[2].children[1];
    expect(token.classList.contains("is-down")).toBe(true);
    expect(token.textContent).toContain("expired");
  });
});
