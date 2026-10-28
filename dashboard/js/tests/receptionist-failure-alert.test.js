import { describe, expect, test } from "bun:test";
import { ReceptionistFailureAlert } from "../implementation/receptionist-failure-alert.js";
import { FakeDocument } from "./_fake-dom.js";

const PLAN = {
  id: "20bf19be",
  agent: "sydney",
  name: "Sydney",
  spoken: "Task 20bf19be failed: the plan I sent to Opus did not run.",
};

function setup(state) {
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
    setInterval: () => 1,
  });
  const cards = () => doc.body.children.flatMap((box) => box.children);
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
    expect(t.cards()[0].children.length).toBe(2); // no Got it button
  });

  test("nothing pending shows nothing; a down dashboard throws nothing", async () => {
    const t = setup({ ok: true, alerts: [], errors: [] });
    await t.alert.poll();
    t.set(new Error("offline"));
    await t.alert.poll();
    expect(t.cards().length).toBe(0);
    expect(t.spoken.length).toBe(0);
  });
});
