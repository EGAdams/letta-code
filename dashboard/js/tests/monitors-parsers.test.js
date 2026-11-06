import { describe, expect, test } from "bun:test";
import { MONITOR_CATALOG } from "../abstract/monitors/sources/monitor-catalog.js";
import { parseAgentActivity } from "../abstract/monitors/sources/parsers/agent-activity-parser.js";
import { parseAgentHealth } from "../abstract/monitors/sources/parsers/agent-health-parser.js";
import { parseBridgePoll } from "../abstract/monitors/sources/parsers/bridge-poll-parser.js";
import { parseCodexSync } from "../abstract/monitors/sources/parsers/codex-sync-parser.js";
import { parseModelStats } from "../abstract/monitors/sources/parsers/model-stats-parser.js";
import { parsePcMetrics } from "../abstract/monitors/sources/parsers/pc-metrics-parser.js";
import { parseReceptionistAlerts } from "../abstract/monitors/sources/parsers/receptionist-alerts-parser.js";
import { parseServerHealth } from "../abstract/monitors/sources/parsers/server-health-parser.js";
import { parseSshHealth } from "../abstract/monitors/sources/parsers/ssh-health-parser.js";
import { parseWorkerActivity } from "../abstract/monitors/sources/parsers/worker-activity-parser.js";

describe("monitor parsers", () => {
  test("pc metrics: busiest metric is the value, worst level wins", () => {
    const s = parsePcMetrics({
      ok: true,
      note: "w11",
      metrics: [
        { label: "RAM", percent: 40, level: "ok", text: "4 GB" },
        { label: "Disk", percent: 91, level: "crit", text: "9 GB free" },
      ],
    });
    expect(s.value).toBe(91);
    expect(s.level).toBe("crit");
    expect(s.items.map((i) => i.label)).toEqual(["RAM", "Disk"]);
  });

  test("stale payloads say so in the detail", () => {
    const s = parsePcMetrics({
      ok: true,
      metrics: [],
      stale: true,
      stale_error: "HTTP 502",
    });
    expect(s.detail).toContain("stale: HTTP 502");
  });

  test("server health: share up, down is critical", () => {
    const s = parseServerHealth({
      servers: [
        { key: "a", status: "up" },
        { key: "b", status: "down" },
      ],
    });
    expect(s.value).toBe(50);
    expect(s.level).toBe("crit");
  });

  test("ssh: a muted link never alerts", () => {
    const s = parseSshHealth({
      connections: [
        { key: "a", status: "up" },
        { key: "b", status: "down", muted: true },
      ],
    });
    expect(s.level).toBe("ok");
    expect(s.segments.map((x) => x.label)).toEqual(["up", "down"]);
  });

  test("agent activity counts only agent- keys", () => {
    const s = parseAgentActivity({
      "agent-1": "idle",
      "agent-2": "error",
      stale: true,
    });
    expect(s.segments).toHaveLength(2);
    expect(s.level).toBe("crit");
  });

  test("agent health lists the unhealthy ones", () => {
    const s = parseAgentHealth({
      "agent-1": { ok: true, name: "A" },
      "agent-2": { ok: false, name: "B", text: "missing tool" },
    });
    expect(s.value).toBe(50);
    expect(s.items).toEqual([
      { label: "B", text: "missing tool", level: "warn" },
    ]);
  });

  test("receptionist alerts are critical; an unreachable sidecar warns", () => {
    expect(
      parseReceptionistAlerts({
        ok: true,
        alerts: [{ message: "x" }],
        errors: [],
      }).level,
    ).toBe("crit");
    expect(
      parseReceptionistAlerts({ ok: true, alerts: [], errors: ["down"] }).level,
    ).toBe("warn");
    expect(
      parseReceptionistAlerts({ ok: true, alerts: [], errors: [] }).value,
    ).toBe(0);
  });

  test("bridge poll: countdown fraction from next_check_at", () => {
    const now = Date.parse("2026-11-04T14:00:00Z");
    const s = parseBridgePoll(
      {
        service: { active: "active" },
        state: {
          next_check_at: "2026-11-04T14:00:30Z",
          delay_seconds: 60,
          outcome: "idle",
        },
      },
      now,
    );
    expect(s.value).toBe(30);
    expect(s.fraction).toBe(0.5);
    expect(s.level).toBe("ok");
    expect(
      parseBridgePoll({ service: { active: "inactive" }, state: {} }).level,
    ).toBe("crit");
  });

  test("model stats: quota left in the tightest window", () => {
    const s = parseModelStats({
      ok: true,
      windows: [
        { label: "5-hour", used_percent: 11 },
        { label: "weekly", used_percent: 75 },
      ],
    });
    expect(s.value).toBe(25);
    expect(s.level).toBe("warn");
    expect(parseModelStats({ ok: false, error: "unknown source" }).level).toBe(
      "unknown",
    );
  });

  test("model stats: a paused (null) window is not read as 0% used", () => {
    const s = parseModelStats({
      ok: true,
      model: "m",
      detail: "plan: plus",
      windows: [
        { label: "5-hour", used_percent: null },
        { label: "weekly", used_percent: 86 },
      ],
    });
    expect(s.value).toBe(14);
    expect(s.items.length).toBe(1);
    expect(s.detail).toBe("m · plan: plus");
    expect(
      parseModelStats({ ok: true, windows: [{ used_percent: null }] }).level,
    ).toBe("unknown");
  });

  test("codex sync needing re-auth is critical", () => {
    expect(
      parseCodexSync({
        interval_seconds: 100,
        seconds_remaining: 25,
        needs_reauth: true,
      }).level,
    ).toBe("crit");
    expect(
      parseCodexSync({ interval_seconds: 100, seconds_remaining: 25 }).fraction,
    ).toBe(0.25);
  });

  test("worker activity: failed tasks are listed and critical", () => {
    const s = parseWorkerActivity({
      tasks: [
        { status: "succeeded", agent: "codex", operation: "inspect" },
        { status: "failed", agent: "codex", operation: "build", error: "boom" },
      ],
    });
    expect(s.level).toBe("crit");
    expect(s.items[0].text).toBe("boom");
  });

  test("every catalog row parses an empty payload without throwing", () => {
    for (const row of MONITOR_CATALOG)
      expect(() => row.parse({})).not.toThrow();
    expect(new Set(MONITOR_CATALOG.map((r) => r.key)).size).toBe(
      MONITOR_CATALOG.length,
    );
  });
});
