import { describe, expect, test } from "bun:test";
import { ReceptionistFailureAlert } from "../implementation/receptionist-failure-alert.js";
import { FakeDocument } from "./_fake-dom.js";

const PLAN = {
  id: "20bf19be",
  agent: "sydney",
  name: "Sydney",
  spoken: "Task 20bf19be failed: the plan I sent to Opus did not run.",
};

function setup(state, opts = {}) {
  const doc = new FakeDocument();
  const posts = [];
  const spoken = [];
  const notified = [];
  let current = state;
  const http = {
    getJSON: async () => {
      if (current instanceof Error) throw current;
      return current;
    },
    postJSON: async (url, body) => {
      posts.push([url, body]);
      return { ok: true, acknowledged: 1 };
    },
  };
  const alert = new ReceptionistFailureAlert({
    http,
    doc,
    speech: { speak: (text, agent) => spoken.push([text, agent]) },
    notify: (title, body) => notified.push([title, body]),
    storage: opts.storage ?? null,
    setInterval: () => 1,
  });
  const cards = () =>
    doc.body.children
      .flatMap((box) => box.children)
      .filter((el) => el.classList.contains("receptionist-failure-alert"));
  return {
    alert,
    doc,
    posts,
    spoken,
    notified,
    cards,
    set: (s) => {
      current = s;
    },
  };
}

describe("ReceptionistFailureAlert", () => {
  test("an alert's own title wins over the failure title", async () => {
    const done = {
      id: "bridge-t_1",
      agent: "toyota",
      name: "Toyota",
      kind: "bridge_finished",
      title: "Star Trek Bridge: Codex writer finished",
      spoken: "The Star Trek Bridge says: done.",
    };
    const t = setup({ ok: true, alerts: [done], errors: [] });
    await t.alert.poll();
    expect(t.notified[0][0]).toBe("Star Trek Bridge: Codex writer finished");
  });

  test("a failed task is shown, spoken and notified once", async () => {
    const t = setup({ ok: true, alerts: [PLAN], errors: [] });
    await t.alert.poll();
    await t.alert.poll();
    expect(t.cards().length).toBe(1);
    expect(t.cards()[0].children[1].textContent).toContain(
      "plan I sent to Opus",
    );
    expect(t.spoken.length).toBe(1);
    expect(t.spoken[0][1]).toBe("sydney");
    expect(t.notified.length).toBe(1);
  });

  test("the same task from two alert sources gets one card but both alerts remain acknowledgeable", async () => {
    const t = setup({
      ok: true,
      alerts: [
        { ...PLAN, agent: "sydney", task_id: "20bf19be" },
        {
          ...PLAN,
          id: "bridge-20bf19be",
          agent: "bridge",
          task_id: "20bf19be",
          severity: "urgent",
          title: "Bridge task failed",
        },
      ],
      errors: [],
    });
    await t.alert.poll();
    expect(t.cards()).toHaveLength(1);
    t.cards()[0].children[2].click();
    await Promise.resolve();
    await Promise.resolve();
    expect(t.posts).toHaveLength(2);
    expect(t.cards()).toHaveLength(0);
  });

  test("Got it acknowledges on the right sidecar and removes the card", async () => {
    const t = setup({ ok: true, alerts: [PLAN], errors: [] });
    await t.alert.poll();
    const ack = t.cards()[0].children[2];
    ack.click();
    await Promise.resolve();
    await Promise.resolve();
    expect(t.posts).toEqual([
      ["/api/receptionist-alerts/ack", { agent: "sydney", ids: ["20bf19be"] }],
    ]);
    expect(t.cards().length).toBe(0);
  });

  test("a card the server stops listing is removed", async () => {
    const t = setup({ ok: true, alerts: [PLAN], errors: [] });
    await t.alert.poll();
    t.set({ ok: true, alerts: [], errors: [] });
    await t.alert.poll();
    expect(t.cards().length).toBe(0);
  });

  test("a receptionist that cannot read her alerts is itself an alert", async () => {
    const t = setup({
      ok: true,
      alerts: [],
      errors: [
        { agent: "toyota", name: "Toyota", error: "PermissionError: alerts" },
      ],
    });
    await t.alert.poll();
    expect(t.cards().length).toBe(1);
    expect(t.cards()[0].children[0].textContent).toContain("can't read");
    expect(
      t.cards()[0].querySelector(".receptionist-failure-alert-ack"),
    ).toBeNull(); // nothing to acknowledge
  });

  test("nothing pending shows nothing; a down dashboard throws nothing", async () => {
    const t = setup({ ok: true, alerts: [], errors: [] });
    await t.alert.poll();
    t.set(new Error("offline"));
    await t.alert.poll();
    expect(t.cards().length).toBe(0);
    expect(t.spoken.length).toBe(0);
  });

  test("the stack fits a phone: never wider or taller than the screen, and scrolls", async () => {
    const t = setup({ ok: true, alerts: [PLAN], errors: [] });
    await t.alert.poll();
    const box = t.doc.body.children[0];
    expect(box.style.width).toContain("100vw");
    expect(box.style.maxHeight).toContain("24px");
    expect(box.style.overflowY).toBe("auto");
  });

  test("the corner close button acknowledges like Got it", async () => {
    const t = setup({ ok: true, alerts: [PLAN], errors: [] });
    await t.alert.poll();
    t.cards()[0].querySelector(".receptionist-failure-alert-close").click();
    await Promise.resolve();
    await Promise.resolve();
    expect(t.posts).toEqual([
      ["/api/receptionist-alerts/ack", { agent: "sydney", ids: ["20bf19be"] }],
    ]);
    expect(t.cards()).toHaveLength(0);
  });

  test("a long message is clamped with Show more; a short one is not", async () => {
    const long = { ...PLAN, id: "long", spoken: "x ".repeat(300) };
    const t = setup({ ok: true, alerts: [PLAN, long], errors: [] });
    await t.alert.poll();
    const [short, big] = t.cards();
    expect(short.querySelector(".receptionist-failure-alert-more")).toBeNull();
    const more = big.querySelector(".receptionist-failure-alert-more");
    const text = big.querySelector(".receptionist-failure-alert-text");
    expect(text.style.WebkitLineClamp).toBe("4");
    more.click();
    expect(text.style.overflow).toBe("visible");
    expect(more.textContent).toBe("Show less");
  });

  test("two or more cards get a Dismiss all bar that acknowledges every one", async () => {
    const other = { ...PLAN, id: "other", agent: "toyota" };
    const t = setup({ ok: true, alerts: [PLAN, other], errors: [] });
    await t.alert.poll();
    const bar = t.doc.body.children[0].children[0];
    expect(bar.classList.contains("receptionist-failure-alerts-bar")).toBe(
      true,
    );
    bar.querySelector(".receptionist-failure-alerts-dismiss-all").click();
    for (let i = 0; i < 6; i++) await Promise.resolve();
    expect(t.posts).toHaveLength(2);
    expect(t.cards()).toHaveLength(0);
    expect(t.doc.body.children[0].children).toHaveLength(0);
  });

  test("an unackable card closes on this page and stays closed while it persists", async () => {
    const state = {
      ok: true,
      alerts: [],
      errors: [{ agent: "toyota", name: "Toyota", error: "boom" }],
    };
    const t = setup(state);
    await t.alert.poll();
    t.cards()[0].querySelector(".receptionist-failure-alert-close").click();
    expect(t.cards()).toHaveLength(0);
    await t.alert.poll();
    expect(t.cards()).toHaveLength(0);
    expect(t.posts).toHaveLength(0);
  });

  test("a reload does not speak an alert this browser already heard", async () => {
    const mem = {};
    const storage = {
      getItem: (k) => mem[k] ?? null,
      setItem: (k, v) => {
        mem[k] = v;
      },
    };
    const first = setup({ ok: true, alerts: [PLAN], errors: [] }, { storage });
    await first.alert.poll();
    expect(first.spoken).toHaveLength(1);
    const reload = setup({ ok: true, alerts: [PLAN], errors: [] }, { storage });
    await reload.alert.poll();
    expect(reload.cards()).toHaveLength(1);
    expect(reload.spoken).toHaveLength(0);
    expect(reload.notified).toHaveLength(0);
  });

  test("only a failure is red: a Bridge task that succeeded gets the calm card", async () => {
    const done = {
      id: "bridge-t_ok",
      task_id: "t_ok",
      agent: "sydney",
      kind: "bridge_finished",
      outcome: "succeeded",
      title: "Star Trek Bridge: ChatGPT relay finished",
      spoken: "bati says: I'm ready, EG.",
    };
    const failed = {
      ...done,
      id: "bridge-t_bad",
      task_id: "t_bad",
      outcome: "failed",
      title: "Star Trek Bridge: browser failed",
    };
    const t = setup({ ok: true, alerts: [done, failed, PLAN], errors: [] });
    await t.alert.poll();
    expect(t.cards().map((c) => c.dataset.tone)).toEqual([
      "done",
      "failed",
      "failed",
    ]);
    expect(t.cards()[0].style.background).not.toBe("#b00020");
    expect(t.cards()[1].style.background).toBe("#b00020");
  });

  test("a task with a success and a failure source stays red", async () => {
    const t = setup({
      ok: true,
      alerts: [
        { ...PLAN, id: "a", task_id: "t1", outcome: "succeeded" },
        { ...PLAN, id: "b", agent: "bridge", task_id: "t1" },
      ],
      errors: [],
    });
    await t.alert.poll();
    expect(t.cards()).toHaveLength(1);
    expect(t.cards()[0].dataset.tone).toBe("failed");
  });
});

const FAILED = {
  id: "f1",
  agent: "sydney",
  name: "Sydney",
  task_id: "t_exec",
  spoken: "Something broke badly.",
};

/** URL-aware double: /api/remediation-models and /api/alert-remediation/dispatch
 * need distinct responses from the alerts poll, unlike the shared `setup()`
 * above (which only ever serves one alerts payload to every getJSON call). */
function setupExecute({
  alerts = [FAILED],
  modelsPayload = {
    current: "claude-sonnet",
    providers: [
      {
        id: "claude-sonnet",
        label: "Claude Sonnet",
        available: false,
        configured: true,
        detail: "",
      },
      {
        id: "claude-opus",
        label: "Claude Opus",
        available: false,
        configured: false,
        detail: "not configured in this deployment",
      },
    ],
  },
  dispatchResponse = {
    ok: true,
    already_submitted: false,
    status: "queued",
    task_id: "remediate-abc123",
  },
  statusResponses = [],
} = {}) {
  const doc = new FakeDocument();
  const posts = [];
  const statusGets = [];
  const timers = [];
  let clock = 0;
  const http = {
    getJSON: async (url) => {
      if (url === "/api/remediation-models") return modelsPayload;
      if (url.startsWith("/api/alert-remediation/status")) {
        statusGets.push(url);
        const next = statusResponses.shift();
        if (next instanceof Error) throw next;
        return next;
      }
      return { ok: true, alerts, errors: [] };
    },
    postJSON: async (url, body) => {
      posts.push([url, body]);
      if (url === "/api/alert-remediation/dispatch") {
        if (dispatchResponse instanceof Error) throw dispatchResponse;
        return dispatchResponse;
      }
      return { ok: true };
    },
  };
  const alert = new ReceptionistFailureAlert({
    http,
    doc,
    setInterval: () => 1,
    setTimeout: (fn, ms) => timers.push({ fn, ms }),
    now: () => clock,
  });
  const card = async () => {
    await alert.poll();
    return doc.body.children[0].children[0];
  };
  /** Runs the next scheduled status poll, advancing the fake clock by its delay. */
  const tick = async () => {
    const next = timers.shift();
    if (!next) return false;
    clock += next.ms;
    await next.fn();
    await settle();
    return true;
  };
  const advance = (ms) => {
    clock += ms;
  };
  return { alert, doc, posts, card, statusGets, timers, tick, advance };
}

async function settle(n = 3) {
  for (let i = 0; i < n; i++) await Promise.resolve();
}

describe("ReceptionistFailureAlert — Execute agent", () => {
  test("a short failing card shows exactly Got it and Execute agent, plus the close icon", async () => {
    const t = setupExecute();
    const card = await t.card();
    const labels = card.querySelectorAll("button").map((b) => b.textContent);
    expect(labels).toEqual(["Got it", "Execute agent", "×"]);
  });

  test("a long failing card adds Show more without losing Got it or Execute agent", async () => {
    const t = setupExecute({
      alerts: [{ ...FAILED, spoken: "x ".repeat(300) }],
    });
    const card = await t.card();
    const labels = card.querySelectorAll("button").map((b) => b.textContent);
    expect(labels).toEqual(["Got it", "Execute agent", "Show more", "×"]);
  });

  test("defaults to Claude Sonnet and disables Opus with the registry's own reason", async () => {
    const t = setupExecute();
    const card = await t.card();
    const select = card.querySelector(
      ".receptionist-failure-alert-model-select",
    );
    expect(select.value).toBe("claude-sonnet");
    await settle();
    const opus = card
      .querySelectorAll("option")
      .find((o) => o.value === "claude-opus");
    expect(opus.disabled).toBe(true);
    expect(opus.textContent).toContain("not configured in this deployment");
  });

  test("Opus is only offered once the registry reports it configured", async () => {
    const t = setupExecute({
      modelsPayload: {
        current: "claude-sonnet",
        providers: [
          {
            id: "claude-sonnet",
            label: "Claude Sonnet",
            available: false,
            configured: true,
            detail: "",
          },
          {
            id: "claude-opus",
            label: "Claude Opus",
            available: false,
            configured: true,
            detail: "",
          },
        ],
      },
    });
    const card = await t.card();
    await settle();
    const opus = card
      .querySelectorAll("option")
      .find((o) => o.value === "claude-opus");
    expect(opus.disabled).toBe(false);
    expect(opus.textContent).toBe("Claude Opus");
  });

  test("the visible prompt is the sanitized one, not raw alert text", async () => {
    const t = setupExecute({
      alerts: [
        {
          ...FAILED,
          spoken: "Authorization: Bearer sk-liveSECRETVALUE123 failed",
        },
      ],
    });
    const card = await t.card();
    const promptBox = card.querySelector(".receptionist-failure-alert-prompt");
    expect(promptBox.value).not.toContain("sk-liveSECRETVALUE123");
    expect(promptBox.value).toContain("[REDACTED]");
  });

  test("clicking Execute agent disables it, posts once and reports the task id back in the UI", async () => {
    const t = setupExecute();
    const card = await t.card();
    const execute = card.querySelector(".receptionist-failure-alert-execute");
    const status = card.querySelector(
      ".receptionist-failure-alert-dispatch-status",
    );

    execute.click();
    expect(execute.disabled).toBe(true); // synchronous, before the POST even resolves
    await settle();

    expect(t.posts).toHaveLength(1);
    const [url, body] = t.posts[0];
    expect(url).toBe("/api/alert-remediation/dispatch");
    expect(body.alert_key).toBe("task:t_exec");
    expect(body.model_id).toBe("claude-sonnet");
    expect(body.prompt).toContain("## Exact error");
    expect(status.textContent).toContain("Submitted");
    expect(status.textContent).toContain("remediate-abc123");
    expect(execute.disabled).toBe(true); // stays disabled: one task per alert
  });

  test("the alert is not auto-dismissed by a successful dispatch", async () => {
    const t = setupExecute();
    const card = await t.card();
    card.querySelector(".receptionist-failure-alert-execute").click();
    await settle();
    expect(
      t.posts.filter(([url]) => url === "/api/receptionist-alerts/ack"),
    ).toHaveLength(0);
    expect(card.parent).not.toBeNull();
  });

  test("a second click while the first is still in flight does not submit twice", async () => {
    const t = setupExecute();
    const card = await t.card();
    const execute = card.querySelector(".receptionist-failure-alert-execute");
    execute.click();
    execute.click();
    await settle();
    expect(t.posts).toHaveLength(1);
  });

  test("a refused dispatch re-enables the button and shows the server's reason", async () => {
    const t = setupExecute({
      dispatchResponse: {
        ok: false,
        error: "model_unavailable",
        detail: '"claude-opus" is not configured',
      },
    });
    const card = await t.card();
    const execute = card.querySelector(".receptionist-failure-alert-execute");
    execute.click();
    await settle();
    expect(execute.disabled).toBe(false); // a refusal is retryable
    expect(
      card.querySelector(".receptionist-failure-alert-dispatch-status")
        .textContent,
    ).toContain("Not executed");
  });

  test("a network failure leaves the copy-paste prompt as the fallback and re-enables the button", async () => {
    const t = setupExecute({ dispatchResponse: new Error("offline") });
    const card = await t.card();
    const execute = card.querySelector(".receptionist-failure-alert-execute");
    execute.click();
    await settle();
    expect(execute.disabled).toBe(false);
    expect(
      card.querySelector(".receptionist-failure-alert-dispatch-status")
        .textContent,
    ).toContain("Copy the prompt below");
  });

  test("a card that already succeeded (done tone) never gets an Execute agent button", async () => {
    const done = { ...FAILED, outcome: "succeeded" };
    const t = setupExecute({ alerts: [done] });
    const card = await t.card();
    expect(
      card.querySelector(".receptionist-failure-alert-execute"),
    ).toBeNull();
  });

  test("the dispatched prompt is exactly the one shown in the box", async () => {
    const t = setupExecute();
    const card = await t.card();
    const shown = card.querySelector(
      ".receptionist-failure-alert-prompt",
    ).value;
    card.querySelector(".receptionist-failure-alert-execute").click();
    await settle();
    expect(t.posts[0][1].prompt).toBe(shown);
  });

  test("after submitting, the card follows the task to success and stops polling", async () => {
    const t = setupExecute({
      dispatchResponse: {
        ok: true,
        already_submitted: false,
        status: "queued",
        task_id: "t_abc",
      },
      statusResponses: [
        { ok: true, task_id: "t_abc", state: "running", terminal: false },
        {
          ok: true,
          task_id: "t_abc",
          state: "succeeded",
          terminal: true,
          succeeded: true,
          summary: "Fixed it.",
        },
      ],
    });
    const card = await t.card();
    const status = card.querySelector(
      ".receptionist-failure-alert-dispatch-status",
    );
    card.querySelector(".receptionist-failure-alert-execute").click();
    await settle();
    expect(status.textContent).toContain("t_abc");
    await t.tick();
    expect(t.statusGets[0]).toBe(
      "/api/alert-remediation/status?alert_key=task%3At_exec",
    );
    expect(status.textContent).toContain("running");
    await t.tick();
    expect(status.textContent).toContain("Completed");
    expect(status.textContent).toContain("Fixed it.");
    expect(t.timers).toHaveLength(0); // terminal: nothing more scheduled
  });

  test("a failed task is reported as failed with the Bridge's reason", async () => {
    const t = setupExecute({
      dispatchResponse: {
        ok: true,
        already_submitted: false,
        status: "queued",
        task_id: "t_abc",
      },
      statusResponses: [
        {
          ok: true,
          task_id: "t_abc",
          state: "failed",
          terminal: true,
          succeeded: false,
          detail: "worker timed out",
        },
      ],
    });
    const card = await t.card();
    const status = card.querySelector(
      ".receptionist-failure-alert-dispatch-status",
    );
    card.querySelector(".receptionist-failure-alert-execute").click();
    await settle();
    await t.tick();
    expect(status.textContent).toContain("ended failed");
    expect(status.textContent).toContain("worker timed out");
    expect(status.textContent).not.toContain("Completed");
  });

  test("an unreachable status endpoint is retried, and watching stops at the time limit", async () => {
    const t = setupExecute({
      dispatchResponse: {
        ok: true,
        already_submitted: false,
        status: "queued",
        task_id: "t_abc",
      },
      statusResponses: [new Error("offline")],
    });
    const card = await t.card();
    const status = card.querySelector(
      ".receptionist-failure-alert-dispatch-status",
    );
    card.querySelector(".receptionist-failure-alert-execute").click();
    await settle();
    await t.tick();
    expect(status.textContent).toContain("status unavailable");
    expect(t.timers).toHaveLength(1); // retried
    t.advance(46 * 60 * 1000);
    await t.tick();
    // the poll that was already due runs once more, then the limit stops the watch
    expect(t.timers).toHaveLength(0);
    expect(status.textContent).toContain("stopped watching");
  });
});
