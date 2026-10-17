import { describe, expect, test } from "bun:test";
import { buildConversationContextRow } from "../implementation/conversation-context-panel.js";
import { FakeDocument } from "./_fake-dom.js";

function build({ getJSON, postJSON, confirm = () => true } = {}) {
  const doc = new FakeDocument();
  const statuses = [];
  const http = {
    getJSON: getJSON || (async () => ({ ok: true, current: 100, max: 1000 })),
    postJSON: postJSON || (async () => ({ ok: true })),
  };
  const { row, refresh } = buildConversationContextRow({
    el: (tag, props) => Object.assign(doc.createElement(tag), props || {}),
    http,
    agentId: "toyota-id",
    showStatus: (msg, isError) => statuses.push({ msg, isError }),
    confirm,
  });
  const fill = row.querySelector(".win98-progress-fill");
  const [saveBtn, clearBtn] = row.querySelectorAll("button");
  return { row, refresh, fill, saveBtn, clearBtn, statuses };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

describe("buildConversationContextRow", () => {
  test("loads current/max on construction and sizes the bar", async () => {
    const ctx = build({
      getJSON: async () => ({ ok: true, current: 500, max: 1000 }),
    });
    await flush();
    expect(ctx.fill.style.width).toBe("50%");
    expect(ctx.row.querySelector(".cc-label").textContent).toContain("50%");
  });

  test("Clear starts disabled", () => {
    const ctx = build();
    expect(ctx.clearBtn.disabled).toBe(true);
  });

  test("a successful Save to Memory enables Clear", async () => {
    const ctx = build({
      postJSON: async () => ({
        ok: true,
        num_messages_before: 40,
        num_messages_after: 3,
      }),
    });
    ctx.saveBtn.click();
    await flush();
    expect(ctx.clearBtn.disabled).toBe(false);
    expect(ctx.statuses.at(-1).msg).toContain("40");
  });

  test("a failed Save keeps Clear disabled", async () => {
    const ctx = build({
      postJSON: async () => ({ ok: false, error: "boom" }),
    });
    ctx.saveBtn.click();
    await flush();
    expect(ctx.clearBtn.disabled).toBe(true);
    expect(ctx.statuses.at(-1)).toEqual({ msg: "boom", isError: true });
  });

  test("Clear is a no-op while disabled, even if clicked directly", async () => {
    const posts = [];
    const ctx = build({
      postJSON: async (url) => {
        posts.push(url);
        return { ok: true };
      },
    });
    ctx.clearBtn.click();
    await flush();
    expect(posts).toEqual([]);
  });

  test("Clear asks for confirmation, then resets to disabled again on success", async () => {
    const confirms = [];
    const posts = [];
    const ctx = build({
      postJSON: async (url) => {
        posts.push(url);
        return url === "/api/agent-compact"
          ? { ok: true, num_messages_before: 10, num_messages_after: 2 }
          : { ok: true };
      },
      confirm: (msg) => {
        confirms.push(msg);
        return true;
      },
    });
    ctx.saveBtn.click();
    await flush();
    ctx.clearBtn.click();
    await flush();
    expect(confirms.length).toBe(1);
    expect(posts).toEqual(["/api/agent-compact", "/api/agent-reset-messages"]);
    expect(ctx.clearBtn.disabled).toBe(true);
    expect(ctx.statuses.at(-1).msg).toBe("Conversation cleared.");
  });

  test("declining the confirmation sends nothing", async () => {
    const posts = [];
    const ctx = build({
      postJSON: async (url) => {
        posts.push(url);
        return url === "/api/agent-compact" ? { ok: true } : { ok: true };
      },
      confirm: () => false,
    });
    ctx.saveBtn.click();
    await flush();
    ctx.clearBtn.click();
    await flush();
    expect(posts).toEqual(["/api/agent-compact"]);
  });

  test("an unreachable context endpoint fails closed with a visible label", async () => {
    const ctx = build({ getJSON: async () => ({ ok: false }) });
    await flush();
    expect(ctx.row.querySelector(".cc-label").textContent).toBe(
      "Context: unavailable",
    );
  });
});
