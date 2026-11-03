import { describe, expect, test } from "bun:test";
import {
  countdown,
  fmtSeconds,
  pollSequenceDiagram,
  progressLabel,
  renderPollPage,
  renderProgressBar,
  renderSettingsTable,
} from "../abstract/agent-bridge-poll-render.js";
import { tabClassFor } from "../boot/agent-bridge-poll.js";

const NOW = Date.parse("2026-10-31T23:32:14-04:00");
const waiting = {
  phase: "waiting",
  outcome: "idle",
  delay_seconds: 30,
  next_check_at: "2026-10-31T23:32:34-04:00",
  checked_at: "2026-10-31T23:32:04-04:00",
  checks: 4,
};

const row = (key, value, inFile = true) => ({
  key,
  label: key,
  help: `help for ${key}`,
  unit: key === "active_hours" ? "" : "s",
  value,
  in_file: inFile,
});

const payload = {
  polling: "active",
  reason: "polling",
  service: { active: "active", enabled: "enabled" },
  state: waiting,
  settings: [
    row("idle_seconds", 30),
    row("burst_seconds", 5),
    row("burst_window_seconds", 300),
    row("slow_down_seconds", 3600),
    row("error_base_seconds", 30),
    row("error_max_seconds", 900),
    row("active_hours", null),
  ],
  settings_path:
    "/home/adamsl/agent_blocks/lancedb_memory/agent_bridge_worker/poll_settings.json",
  restart_command: "systemctl --user restart agent-bridge-worker.service",
  settings_changed_since_start: false,
  settings_error: "",
};

describe("countdown", () => {
  test("is halfway through a 30 s wait with 20 s left", () => {
    const c = countdown(waiting, NOW);
    expect(c.mode).toBe("waiting");
    expect(c.secondsLeft).toBeCloseTo(20, 5);
    expect(c.fraction).toBeCloseTo(1 / 3, 5);
  });

  test("uses the server clock offset, not the phone's", () => {
    // Phone runs 10 s slow: server says it is 10 s later than the phone thinks.
    expect(countdown(waiting, NOW, 10000).secondsLeft).toBeCloseTo(10, 5);
  });

  test("is due once the time has passed", () => {
    expect(countdown(waiting, NOW + 60000).mode).toBe("due");
  });

  test("working and stopped have no countdown", () => {
    expect(countdown({ phase: "working" }, NOW).mode).toBe("working");
    expect(countdown({ phase: "stopped" }, NOW).mode).toBe("stopped");
    expect(countdown(null, NOW).mode).toBe("unknown");
  });
});

describe("progress bar", () => {
  test("is solid fill at the elapsed width with a seconds label", () => {
    const html = renderProgressBar(countdown(waiting, NOW));
    expect(html).toContain('class="w2k-progress"');
    expect(html).toContain("width:33.3%");
    expect(html).toContain("20 s until the next check");
  });

  test("labels long waits in minutes and hours", () => {
    expect(fmtSeconds(3600)).toBe("60 min 0 s");
    expect(fmtSeconds(4 * 3600)).toBe("4 h 0 min");
    expect(progressLabel({ mode: "working" })).toContain("Running a task");
  });
});

describe("settings table", () => {
  test("shows every setting and how to change them", () => {
    const html = renderSettingsTable(payload);
    for (const key of [
      "idle_seconds",
      "burst_seconds",
      "burst_window_seconds",
      "slow_down_seconds",
      "error_base_seconds",
      "error_max_seconds",
      "active_hours",
    ])
      expect(html).toContain(key);
    expect(html).toContain("3600 s (60 min 0 s)");
    expect(html).toContain("Around the clock");
    expect(html).toContain("doubling");
    expect(html).toContain(
      "systemctl --user restart agent-bridge-worker.service",
    );
  });

  test("names active hours as ignore times", () => {
    const p = {
      ...payload,
      settings: [row("active_hours", { start_hour: 7, end_hour: 24 })],
    };
    expect(renderSettingsTable(p)).toContain("07:00 to midnight");
    expect(renderSettingsTable(p)).not.toContain("overnight");
  });

  test("says when active hours run overnight", () => {
    const p = {
      ...payload,
      settings: [row("active_hours", { start_hour: 22, end_hour: 6 })],
    };
    expect(renderSettingsTable(p)).toContain("22:00 to 06:00 (overnight)");
  });

  test("warns when the file changed after the worker started", () => {
    expect(
      renderSettingsTable({ ...payload, settings_changed_since_start: true }),
    ).toContain("Restart it");
  });

  test("escapes what it shows", () => {
    expect(renderSettingsTable({ ...payload, settings_path: "<x>" })).toContain(
      "&lt;x&gt;",
    );
  });
});

describe("page and diagram", () => {
  test("page has the bar, settings, doc and a diagram host", () => {
    const html = renderPollPage(payload, countdown(waiting, NOW));
    expect(html).toContain("w2k-progress");
    expect(html).toContain("abp-settings");
    expect(html).toContain("StarTrekBridge");
    expect(html).toContain('id="abp-diagram"');
  });

  test("diagram is a sequence diagram with the live numbers and no semicolons", () => {
    const code = pollSequenceDiagram({
      ...payload,
      settings: [row("idle_seconds", 45)],
    });
    expect(code.startsWith("sequenceDiagram")).toBe(true);
    expect(code).toContain("loop every 45 s while idle");
    expect(code).toContain("wait 60 min");
    expect(code).not.toContain(";");
  });
});

describe("tab colour", () => {
  test("green only when actively polling, grey otherwise", () => {
    expect(tabClassFor(payload)).toBe("server-up");
    expect(tabClassFor({ ...payload, polling: "paused" })).toBe(
      "poll-disabled",
    );
    expect(tabClassFor({ ...payload, polling: "disabled" })).toBe(
      "poll-disabled",
    );
    expect(tabClassFor(null)).toBe("poll-disabled");
  });
});
