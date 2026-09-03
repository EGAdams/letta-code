import { describe, expect, test } from "bun:test";
import {
  AgentAssignmentsController,
  buildOauthAccountSelect,
} from "../implementation/agent-assignments-panel.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(rows) {
  const doc = new FakeDocument();
  const container = doc.createElement("div");
  const http = { getJSON: async () => rows };
  const controller = new AgentAssignmentsController({
    http,
    el: (tag, props = {}) => Object.assign(doc.createElement(tag), props),
    container,
    setInterval: () => 1,
    clearInterval: () => {},
  });
  return { container, controller };
}

describe("AgentAssignmentsController tool rows", () => {
  test("renders an expired Mazda provider explicitly instead of a question mark", async () => {
    const { container, controller } = setup([
      {
        id: "agent-mazda",
        name: "Mazda",
        model: "gpt-5.6-sol",
        account_label: "eg1972@gmail.com",
        weekly_percent_remaining: null,
        token_status: "down",
        token_status_detail: "Letta provider token expired",
      },
    ]);

    await controller.poll();

    const label =
      container.querySelector("tbody").children[0].children[3].children[0]
        .children[1];
    expect(label.textContent).toContain("expired");
    expect(label.textContent).not.toBe("?");
  });

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

  test("renders a rate-limited Claude token as a live countdown, not 'Unavailable'", async () => {
    const { container, controller } = setup([
      {
        id: "agent-mazda",
        name: "Mazda",
        model: "claude-sonnet-5",
        account_label: "eg1972@gmail.com",
        weekly_percent_remaining: null,
        token_status: null,
        token_status_detail: "Usage reporting rate limited — resets in 24m",
        token_reset_at: 1700001494,
      },
    ]);

    await controller.poll();

    const row = container.querySelector("tbody").children[0];
    const barTd = row.children[3];
    const fill = barTd.children[0].children[0];
    const label = barTd.children[0].children[1];
    expect(fill.classList.contains("is-pending")).toBe(true);
    expect(fill.classList.contains("is-critical")).toBe(false);
    expect(label.innerHTML).toContain('data-countdown-until="1700001494"');
  });

  test("renders an unassigned OAuth account as a read-only row", async () => {
    const { container, controller } = setup([
      {
        id: "oauth-account-chatgpt-plus-pro-mom",
        name: "rbarnesrol@aol.com",
        model: "No ChatGPT Assigned",
        account: "mom",
        account_label: "rbarnesrol@aol.com",
        weekly_percent_remaining: 62,
        assignment_kind: "account",
      },
    ]);

    await controller.poll();

    const row = container.querySelector("tbody").children[0];
    expect(row.children[0].textContent).toBe("rbarnesrol@aol.com");
    expect(row.children[1].textContent).toBe("No ChatGPT Assigned");
    expect(row.children[2].textContent).toBe("rbarnesrol@aol.com");
    expect(row.querySelector("select")).toBe(null);
  });

  test("renders a rate-limited unassigned account with a countdown instead of '?'", async () => {
    const { container, controller } = setup([
      {
        id: "oauth-account-claude-pro-max-eg",
        name: "eg1972@gmail.com",
        model: "No Claude Assigned",
        account: "eg",
        account_label: "eg1972@gmail.com",
        weekly_percent_remaining: null,
        token_reset_at: 1700001494,
        assignment_kind: "account",
      },
    ]);

    await controller.poll();

    const row = container.querySelector("tbody").children[0];
    const barTd = row.children[3];
    const fill = barTd.children[0].children[0];
    const label = barTd.children[0].children[1];
    expect(fill.classList.contains("is-pending")).toBe(true);
    expect(label.innerHTML).toContain('data-countdown-until="1700001494"');
  });
});

describe("buildOauthAccountSelect", () => {
  function fakeEl(doc) {
    return (tag, props = {}) => Object.assign(doc.createElement(tag), props);
  }

  test("lists every provider across both families, not just the agent's current one", async () => {
    const doc = new FakeDocument();
    const http = {
      getJSON: async () => ({
        ok: true,
        current: "claude-pro-max",
        options: [
          {
            provider: "claude-pro-max-eg",
            account: "eg",
            label: "eg1972@gmail.com",
          },
          {
            provider: "claude-pro-max",
            account: "mom",
            label: "rbarnesrol@gmail.com",
          },
          {
            provider: "chatgpt-plus-pro",
            account: "eg",
            label: "eg1972@gmail.com",
          },
          {
            provider: "chatgpt-plus-pro-mom",
            account: "mom",
            label: "rbarnesrol@aol.com",
          },
        ],
      }),
    };

    const { select } = buildOauthAccountSelect({
      el: fakeEl(doc),
      http,
      agentId: "agent-x",
      showStatus: () => {},
    });
    await new Promise((r) => setTimeout(r, 0));

    const labels = Array.from(select.children).map((o) => o.textContent);
    expect(labels).toContain("rbarnesrol@aol.com");
    expect(select.value).toBe("claude-pro-max");
  });

  test("a cross-family switch calls onSwitched with the server's new model handle", async () => {
    const doc = new FakeDocument();
    const http = {
      getJSON: async () => ({
        ok: true,
        current: "claude-pro-max",
        options: [
          {
            provider: "claude-pro-max",
            account: "mom",
            label: "rbarnesrol@gmail.com",
          },
          {
            provider: "chatgpt-plus-pro-mom",
            account: "mom",
            label: "rbarnesrol@aol.com",
          },
        ],
      }),
      postJSON: async () => ({
        ok: true,
        account: "mom",
        provider: "chatgpt-plus-pro-mom",
        model: "chatgpt-plus-pro-mom/gpt-5.6-sol",
      }),
    };
    let switched = null;

    const { select } = buildOauthAccountSelect({
      el: fakeEl(doc),
      http,
      agentId: "agent-x",
      showStatus: () => {},
      onSwitched: (result) => {
        switched = result;
      },
    });
    await new Promise((r) => setTimeout(r, 0));

    select.value = "chatgpt-plus-pro-mom";
    select.dispatch("change", {});
    await new Promise((r) => setTimeout(r, 0));

    expect(switched?.model).toBe("chatgpt-plus-pro-mom/gpt-5.6-sol");
    expect(select.value).toBe("chatgpt-plus-pro-mom");
  });
});
