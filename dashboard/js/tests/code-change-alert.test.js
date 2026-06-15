import { describe, expect, test } from "bun:test";
import { CodeChangeAlert } from "../implementation/code-change-alert.js";
import { FakeDocument } from "./_fake-dom.js";

function setup(codeStatus) {
  const doc = new FakeDocument();
  const mk = (id) => {
    const el = doc.createElement("button");
    el.id = id;
    return el;
  };
  const tab = mk("btn-agents-home");
  const modal = mk("code-change-modal");
  modal.classList.add("hidden");
  const yes = mk("code-change-yes");
  const no = mk("code-change-no");

  const posts = [];
  const http = {
    getJSON: async () => {
      if (codeStatus instanceof Error) throw codeStatus;
      return typeof codeStatus === "function" ? codeStatus() : codeStatus;
    },
    postJSON: async (url, body) => {
      posts.push({ url, body });
      return { ok: true };
    },
  };
  const alert = new CodeChangeAlert({
    http,
    doc,
    setInterval: () => 1,
  });
  return { alert, tab, modal, yes, no, posts, doc };
}

describe("CodeChangeAlert", () => {
  test("requires an HttpClient", () => {
    expect(() => new CodeChangeAlert({})).toThrow();
  });

  test("blinks the tab and shows the modal when code changed", async () => {
    const ctx = setup({ changed: true, changed_files: ["server.py"] });
    ctx.alert.start();
    await ctx.alert.poll();
    expect(ctx.tab.classList.contains("tab-alert")).toBe(true);
    expect(ctx.modal.classList.contains("hidden")).toBe(false);
  });

  test("'No' dismisses the current signature so it stops re-prompting", async () => {
    const ctx = setup({ changed: true, changed_files: ["server.py"] });
    ctx.alert.start();
    await ctx.alert.poll();
    ctx.no.click(); // dismiss
    expect(ctx.modal.classList.contains("hidden")).toBe(true);
    // Same signature again → no re-prompt.
    await ctx.alert.poll();
    expect(ctx.modal.classList.contains("hidden")).toBe(true);
    expect(ctx.tab.classList.contains("tab-alert")).toBe(false);
  });

  test("'Yes' posts a dashboard restart", async () => {
    const ctx = setup({ changed: true, changed_files: ["x"] });
    ctx.alert.start();
    ctx.yes.click();
    await Promise.resolve();
    expect(ctx.posts[0]).toEqual({
      url: "/api/server-action",
      body: { server: "dashboard", action: "restart" },
    });
  });

  test("clearing the change forgets the dismissal", async () => {
    let changed = true;
    const ctx = setup(() => ({
      changed,
      changed_files: changed ? ["a"] : [],
    }));
    ctx.alert.start();
    await ctx.alert.poll();
    changed = false;
    await ctx.alert.poll();
    expect(ctx.tab.classList.contains("tab-alert")).toBe(false);
    expect(ctx.modal.classList.contains("hidden")).toBe(true);
  });

  test("a fetch failure is swallowed", async () => {
    const ctx = setup(new Error("boom"));
    ctx.alert.start();
    await expect(ctx.alert.poll()).resolves.toBeUndefined();
  });
});
