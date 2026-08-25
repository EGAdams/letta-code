import { describe, expect, test } from "bun:test";
import {
  fmtCountdown,
  renderModelStats,
  renderRateOfChange,
  resetEpoch,
} from "../abstract/model-stats-render.js";
import { renderPcMetrics } from "../abstract/pc-metrics-render.js";

describe("renderRateOfChange", () => {
  test("shows the server's reason, not an empty bar, while history is short", () => {
    const h = renderRateOfChange({
      available: false,
      reason: "gathering data…",
    });
    expect(h).toContain("gathering data…");
    expect(h).toContain("width:0%");
  });

  test("blinks yellow once burn crosses the warn threshold", () => {
    const warm = renderRateOfChange({
      available: true,
      pct_per_hour: 12,
      burn_multiple: 2.4,
      bar_percent: 80,
      warn: true,
    });
    expect(warm).toContain("ms-blink-warn");
    expect(warm).toContain("#f9a825");
    expect(warm).toContain("2.4× pace ⚠");
  });

  test("a missing rate renders nothing at all", () => {
    expect(renderRateOfChange(null)).toBe("");
  });
});

describe("renderModelStats", () => {
  test("an error payload is reported, not silently blank", () => {
    expect(renderModelStats({ ok: false, error: "no session" })).toContain(
      "no session",
    );
    expect(renderModelStats(null)).toContain("no data");
  });

  test("a 429 gets the loud rate-limit banner with a live countdown", () => {
    const h = renderModelStats({
      label: "Codex",
      key: "codex",
      status: "down",
      rate_limited: true,
      rate_limited_until: 1_700_000_000,
    });
    expect(h).toContain("RATE LIMITED (HTTP 429)");
    expect(h).toContain('data-countdown-until="1700000000"');
    // The MAXED OUT line is for quota exhaustion, not a provider 429.
    expect(h).not.toContain("MAXED OUT");
  });

  test("MAXED OUT names the window that is actually full, not the first one", () => {
    const h = renderModelStats({
      label: "Codex",
      key: "codex",
      status: "down",
      windows: [
        { label: "5-hour", used_percent: 10, resets_in: "in 1h" },
        { label: "weekly", used_percent: 100, resets_in: "in 3d" },
      ],
    });
    expect(h).toContain("weekly resets in 3d");
    expect(h).not.toContain("5-hour resets");
  });

  test("window bars go green / yellow / red by usage", () => {
    const h = renderModelStats({
      label: "x",
      key: "x",
      windows: [
        { label: "a", used_percent: 10 },
        { label: "b", used_percent: 85 },
        { label: "c", used_percent: 100 },
      ],
    });
    expect(h).toContain("#43a047");
    expect(h).toContain("#f9a825");
    expect(h).toContain("#e53935");
  });

  test("label and error text are HTML-escaped", () => {
    expect(renderModelStats({ ok: false, error: "<img src=x>" })).not.toContain(
      "<img",
    );
  });
});

describe("countdown helpers", () => {
  test("fmtCountdown drops the hour segment under an hour", () => {
    expect(fmtCountdown(59)).toBe("0:59");
    expect(fmtCountdown(3661)).toBe("1:01:01");
  });

  test("resetEpoch passes numbers through and parses ISO strings", () => {
    expect(resetEpoch(1_700_000_000)).toBe(1_700_000_000);
    expect(resetEpoch("1970-01-01T00:01:00Z")).toBe(60);
    expect(resetEpoch("not a date")).toBeNull();
    expect(resetEpoch(null)).toBeNull();
  });
});

describe("renderPcMetrics", () => {
  test("a critical metric is flagged red and blinking", () => {
    const h = renderPcMetrics({
      label: "Windows 11",
      level: "crit",
      metrics: [
        { label: "Hard Drive", percent: 99, level: "crit", alert: true },
      ],
    });
    expect(h).toContain("⚠ critical");
    expect(h).toContain("#e53935");
    expect(h).toContain("ms-blink-warn");
  });

  test("a stale sample says so instead of passing off old numbers as live", () => {
    const h = renderPcMetrics({
      label: "Moms 46",
      stale: true,
      stale_error: "ssh timeout",
      metrics: [],
    });
    expect(h).toContain("last good reading");
    expect(h).toContain("ssh timeout");
  });

  test("an error payload is reported", () => {
    expect(renderPcMetrics({ ok: false, error: "unreachable" })).toContain(
      "unreachable",
    );
  });
});
