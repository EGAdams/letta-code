import { describe, expect, test } from "bun:test";
import { createStartupGate } from "../abstract/startup-gate.js";
import { FakeDocument } from "./_fake-dom.js";

//: Both dashboard gates (server/SSH preload, agent roster) are this factory
//: with a different task list — the tests below drive it as the agent gate,
//: whose extra behaviour is `resettable`.
function setup({ tasks, resettable = false } = {}) {
  const doc = new FakeDocument();
  doc.body = doc.createElement("body");
  const elements = {
    overlay: doc.createElement("div"),
    statusText: doc.createElement("div"),
    progressBar: doc.createElement("div"),
    console: doc.createElement("div"),
  };
  const timers = [];
  const win = {
    setTimeout: (fn) => {
      timers.push(fn);
      return timers.length;
    },
    clearTimeout: () => {},
  };
  const gate = createStartupGate({
    doc,
    win,
    elements,
    resettable,
    tasks: tasks || [
      {
        key: "agents",
        label: "Loading agents",
        detail: "Fetching agent definitions",
      },
    ],
    labels: {
      running: "Running Agent Management checks...",
      starting: "Checking agent roster...",
      advancing: "Advancing agent checks",
      finished: "Finished loading agents.",
      finishedLine: "finished loading agents.",
    },
  });
  // Every pending timer fires immediately, so finish() resolves in one turn.
  const flush = async () => {
    for (let i = 0; i < 10; i++) {
      while (timers.length) timers.shift()();
      await Promise.resolve();
    }
  };
  return { gate, doc, elements, flush };
}

describe("createStartupGate", () => {
  test("start() marks the page loading and announces the run", () => {
    const { gate, doc, elements } = setup();
    gate.start();
    expect(doc.body.classList.contains("startup-loading")).toBe(true);
    expect(elements.statusText.textContent).toBe(
      "Running Agent Management checks...",
    );
  });

  test("complete() logs the task and advances the status line", () => {
    const { gate, elements } = setup({
      tasks: [
        { key: "a", label: "A", detail: "doing a" },
        { key: "b", label: "B", detail: "doing b" },
      ],
    });
    gate.start();
    gate.complete("a", "Loaded 3 agents.");
    expect(elements.console.children.at(-1).textContent).toContain(
      "Loaded 3 agents.",
    );
    expect(elements.statusText.textContent).toBe("doing a");
  });

  test("fail() still counts the task, so one dead check cannot hang the overlay", async () => {
    const { gate, elements, flush } = setup();
    gate.start();
    gate.fail("agents", new Error("boom"));
    await flush();
    expect(
      elements.console.children.some((l) =>
        l.textContent.includes("Loading agents failed: boom"),
      ),
    ).toBe(true);
    expect(elements.overlay.classList.contains("hidden")).toBe(true);
  });

  test("the last completed task releases the overlay", async () => {
    const { gate, doc, elements, flush } = setup();
    gate.start();
    gate.complete("agents");
    await flush();
    expect(elements.statusText.textContent).toBe("Finished loading agents.");
    expect(elements.overlay.classList.contains("startup-complete")).toBe(true);
    expect(doc.body.classList.contains("startup-loading")).toBe(false);
  });

  test("a released gate ignores further reports", async () => {
    const { gate, elements, flush } = setup();
    gate.start();
    gate.complete("agents");
    await flush();
    const lines = elements.console.children.length;
    gate.complete("agents", "again");
    expect(elements.console.children.length).toBe(lines);
  });

  test("resettable gates re-arm on the next start(); plain ones stay released", async () => {
    const reopening = setup({ resettable: true });
    reopening.gate.start();
    reopening.gate.complete("agents");
    await reopening.flush();
    reopening.gate.start();
    expect(reopening.elements.overlay.classList.contains("hidden")).toBe(false);
    expect(reopening.elements.console.children.length).toBe(0);

    const oneShot = setup();
    oneShot.gate.start();
    oneShot.gate.complete("agents");
    await oneShot.flush();
    oneShot.gate.start();
    oneShot.gate.complete("agents", "second run");
    expect(
      oneShot.elements.console.children.some((l) =>
        l.textContent.includes("second run"),
      ),
    ).toBe(false);
  });
});
