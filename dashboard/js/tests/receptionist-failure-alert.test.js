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
