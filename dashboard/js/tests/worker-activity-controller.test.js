import { describe, expect, test } from "bun:test";
import { createWorkerActivity } from "../boot/worker-activity.js";

// Minimal DOM: the body's parts exist once the page HTML has been written.
function el() {
  const node = { writes: 0, _html: "", textContent: "", listeners: {} };
  node.classList = {
    set: new Set(),
    add: (...c) => {
      for (const x of c) node.classList.set.add(x);
    },
    remove: (...c) => {
      for (const x of c) node.classList.set.delete(x);
    },
    contains: (c) => node.classList.set.has(c),
  };
  Object.defineProperty(node, "innerHTML", {
    get: () => node._html,
    set: (v) => {
      node._html = v;
      node.writes += 1;
    },
  });
  node.addEventListener = (type, fn) => {
    node.listeners[type] = fn;
  };
  return node;
}

function fakeEnv(answers) {
  const body = el();
  const parts = {};
  body.querySelector = (selector) => {
    const name = selector.match(/data-worker-part="(\w+)"/)?.[1];
    if (!name || !body._html.includes(`data-worker-part="${name}"`))
      return null;
    parts[name] ||= el();
    return parts[name];
  };
  const nodes = {
    "worker-activity-body": body,
    "btn-worker-activity": el(),
    "worker-legend": el(),
    "worker-activity": el(),
  };
  const doc = {
    visibilityState: "visible",
    getElementById: (id) => nodes[id] || null,
    addEventListener() {},
  };
  const timers = [];
  const win = {
    setTimeout: (fn, ms) => {
      timers.push({ fn, ms, live: true });
      return timers.length;
    },
    clearTimeout: (id) => {
      if (timers[id - 1]) timers[id - 1].live = false;
    },
  };
  let calls = 0;
  const pending = [];
  const http = {
    getJSON: () => {
      calls += 1;
      const answer = answers[Math.min(calls - 1, answers.length - 1)];
      return new Promise((resolve, reject) =>
        pending.push(() =>
          answer instanceof Error ? reject(answer) : resolve(answer),
        ),
      );
    },
  };
  const flush = async () => {
    while (pending.length) pending.shift()();
    await new Promise((r) => setTimeout(r, 0));
  };
  return { doc, win, http, nodes, parts, timers, flush, calls: () => calls };
}

const ledger = (status) => ({
  ok: true,
  tasks_available: true,
  tasks: [{ id: "t1", agent: "codex", status }],
  worker: {
    status: "active",
    reason: "polling",
    service: { active: "active" },
  },
});

describe("Worker Activity controller", () => {
  test("never overlaps requests and keeps one live timer", async () => {
    const env = fakeEnv([ledger("running")]);
    const wkr = createWorkerActivity(env);
    void wkr.open();
    void wkr.poll();
    expect(env.calls()).toBe(1);
    await env.flush();
    expect(env.timers.filter((t) => t.live).length).toBe(1);
  });

  test("polls fast only while the page is active", async () => {
    const env = fakeEnv([ledger("running")]);
    createWorkerActivity(env);
    await env.flush();
    expect(env.timers.at(-1).ms).toBe(20000);
    env.nodes["worker-activity"].classList.add("active");
    await env.timers.at(-1).fn();
    await env.flush();
    expect(env.timers.at(-1).ms).toBe(5000);
  });

  test("updates legend and SVG on change only, and feeds subscribers", async () => {
    const env = fakeEnv([
      ledger("running"),
      ledger("running"),
      ledger("failed"),
    ]);
    const wkr = createWorkerActivity(env);
    const seen = [];
    wkr.subscribe((p) => seen.push(p.tasks[0].status));
    await env.flush();
    expect(env.nodes["worker-legend"].innerHTML).toContain("running");
    expect(env.nodes["worker-activity-body"].innerHTML).toContain("<svg");
    void wkr.poll();
    await env.flush();
    expect(env.parts.workflow?.writes ?? 0).toBe(0); // same tasks: no redraw
    void wkr.poll();
    await env.flush();
    expect(env.parts.workflow.writes).toBe(1);
    expect(env.parts.workflow.innerHTML).toContain("is-failed");
    expect(env.nodes["worker-legend"].innerHTML).toContain("failed");
    expect(seen).toEqual(["running", "running", "failed"]);
  });

  test("a failed request keeps the SVG and says why", async () => {
    const env = fakeEnv([new Error("HTTP 502")]);
    createWorkerActivity(env);
    await env.flush();
    const html = env.nodes["worker-activity-body"].innerHTML;
    expect(html).toContain("<svg");
    expect(html).toContain("HTTP 502");
    expect(
      env.nodes["btn-worker-activity"].classList.contains("poll-disabled"),
    ).toBe(true);
  });
});
