import { describe, expect, test } from "bun:test";
import { MONITOR_CATALOG } from "../abstract/monitors/sources/monitor-catalog.js";
import { parsePcMetrics } from "../abstract/monitors/sources/parsers/pc-metrics-parser.js";
import { presetSnapshot } from "../abstract/monitors/sources/preset-snapshot.js";
import { pushButtonBankSvg } from "../abstract/monitors/svg/push-button-bank-svg.js";

const reading = parsePcMetrics({
  ok: true,
  metrics: [
    { key: "ram", label: "RAM", percent: 65.6, level: "ok" },
    { key: "disk", label: "Disk", percent: 98.2, level: "warn" },
    { key: "net", label: "Net", percent: 0, level: "ok" },
  ],
});

describe("preset buttons", () => {
  test("a preset narrows the gauge to that metric, keeping 0 as 0", () => {
    expect(presetSnapshot(reading, "ram").value).toBe(65.6);
    expect(presetSnapshot(reading, "disk").level).toBe("warn");
    expect(presetSnapshot(reading, "net").value).toBe(0);
  });

  test("max (or none) is the busiest metric; a missing one is no value", () => {
    expect(presetSnapshot(reading, "max").value).toBe(98.2);
    expect(presetSnapshot(reading, null)).toBe(reading);
    const gone = presetSnapshot(reading, "gpu");
    expect(gone.value).toBeNull();
    expect(gone.level).toBe("unknown");
  });

  test("machines default to SSD with RAM, SSD, NETWORK, MAX", () => {
    for (const row of MONITOR_CATALOG.filter((r) => r.group === "Machines")) {
      expect(row.preset).toBe("disk");
      expect(row.presets.map((p) => p.label)).toEqual([
        "RAM",
        "SSD",
        "NETWORK",
        "MAX",
      ]);
    }
  });

  test("the bank is a radio group with exactly the selected key pressed", () => {
    const svg = pushButtonBankSvg(
      [
        { key: "ram", label: "RAM" },
        { key: "disk", label: "SSD" },
      ],
      "disk",
    );
    expect(svg).toContain('role="radiogroup"');
    expect(svg.match(/role="radio"/g)).toHaveLength(2);
    expect(svg.match(/aria-checked="true"/g)).toHaveLength(1);
    expect(svg).toContain(
      'data-key="disk" role="radio" tabindex="0" aria-checked="true"',
    );
  });
});
