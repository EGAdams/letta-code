import { describe, expect, test } from "bun:test";
import {
  CodexWatchdogController,
  formatElapsed,
  formatTimestamp,
  sessionStatusClass,
} from "../implementation/codex-watchdog-controller.js";
import { FakeDocument } from "./_fake-dom.js";

const IDS = [
  "codex-watchdog-summary",
  "codex-watchdog-sessions",
  "codex-watchdog-actions",
  "codex-watchdog-note",
];

function setup(payload) {
  const doc = new FakeDocument();
  for (const id of IDS) doc.createElement("div").id = id;
  const controller = new CodexWatchdogController({
    doc,
    http: {
      getJSON: async () => {
        if (payload instanceof Error) throw payload;
        return payload;
      },
    },
    setInterval: () => 1,
    clearInterval: () => {},
  });
  return { doc, controller };
}

function session(overrides = {}) {
  return {
    pgid: 1,
    cmd: "node bin/codex --dangerously-bypass-approvals-and-sandbox",
    cwd: "/home/adamsl/letta-code",
    state: "Sl+",
    elapsed_seconds: 90,
    autonomous: true,
    session_path: "/s/a.jsonl",
    primary_used_percent: 10,
    secondary_used_percent: 5,
    ...overrides,
  };
}

function action(overrides = {}) {
  return {
    timestamp: 1_788_793_404,
    action: "terminate_quota",
    pgid: 2,
    cmd: "node bin/codex",
    reason: "97% of 5h Codex quota used (limit 90%)",
    used_percent: 97,
    ...overrides,
  };
}

describe("formatElapsed", () => {
  test("scales seconds/minutes/hours the way the incident's durations needed", () => {
    expect(formatElapsed(45)).toBe("45s");
    expect(formatElapsed(730)).toBe("12m 10s");
    expect(formatElapsed(4896)).toBe("1h 21m");
  });
});

describe("formatTimestamp", () => {
  test("a zero/missing timestamp says so instead of showing the epoch", () => {
    expect(formatTimestamp(0)).toBe("unknown time");
    expect(formatTimestamp(undefined)).toBe("unknown time");
  });
});

describe("sessionStatusClass", () => {
  test("a watched session is never a risk colour, regardless of quota", () => {
    expect(
      sessionStatusClass(
        session({ autonomous: false, primary_used_percent: 99 }),
      ),
    ).toBe("is-watched");
  });

  test("stopped outranks quota -- it is a risk even at 0% usage", () => {
    expect(
      sessionStatusClass(session({ state: "Tl", primary_used_percent: 0 })),
    ).toBe("is-stopped");
  });

  test("quota bands match the daemon's own kill/warn thresholds", () => {
    expect(sessionStatusClass(session({ primary_used_percent: 10 }))).toBe(
      "is-ok",
    );
    expect(sessionStatusClass(session({ primary_used_percent: 75 }))).toBe(
      "is-warning",
    );
    expect(sessionStatusClass(session({ primary_used_percent: 97 }))).toBe(
      "is-critical",
    );
  });
});

describe("CodexWatchdogController", () => {
  test("renders the summary, one row per session, and the thresholds note", async () => {
    const { doc, controller } = setup({
      ok: true,
      sessions: [session(), session({ pgid: 2, primary_used_percent: 97 })],
      recent_actions: [],
      thresholds: { kill_percent: 90, warn_percent: 70, max_concurrent: 1 },
    });

    await controller.poll();

    expect(doc.getElementById("codex-watchdog-summary").textContent).toBe(
      "2 autonomous sessions running — 1 at risk",
    );
    expect(
      doc
        .getElementById("codex-watchdog-summary")
        .classList.contains("is-warning"),
    ).toBe(true);
    expect(doc.getElementById("codex-watchdog-sessions").children.length).toBe(
      2,
    );
    expect(doc.getElementById("codex-watchdog-note").textContent).toContain(
      "Kill ≥90%",
    );
  });

  test("an empty box says so plainly instead of an empty panel", async () => {
    const { doc, controller } = setup({
      ok: true,
      sessions: [],
      recent_actions: [],
      thresholds: {},
    });

    await controller.poll();

    expect(doc.getElementById("codex-watchdog-summary").textContent).toBe(
      "No autonomous Codex sessions running",
    );
    expect(doc.getElementById("codex-watchdog-sessions").children.length).toBe(
      1,
    );
    expect(
      doc.getElementById("codex-watchdog-sessions").children[0].textContent,
    ).toContain("No Codex CLI processes detected");
  });

  test("recent actions render newest first with kill/warn colouring", async () => {
    const { doc, controller } = setup({
      ok: true,
      sessions: [],
      recent_actions: [
        action({ pgid: 1, action: "warn_quota", timestamp: 1 }),
        action({ pgid: 2, action: "terminate_quota", timestamp: 2 }),
      ],
      thresholds: {},
    });

    await controller.poll();

    const rows = doc.getElementById("codex-watchdog-actions").children;
    expect(rows.length).toBe(2);
    expect(rows[0].children[0].textContent).toContain("terminate_quota");
    expect(rows[0].classList.contains("is-kill")).toBe(true);
    expect(rows[1].classList.contains("is-warn")).toBe(true);
  });

  test("a failed fetch is reported, not silently frozen", async () => {
    const { doc, controller } = setup(new Error("network down"));

    await controller.poll();

    expect(doc.getElementById("codex-watchdog-summary").textContent).toBe(
      "unavailable",
    );
    expect(doc.getElementById("codex-watchdog-note").textContent).toContain(
      "network down",
    );
  });
});
