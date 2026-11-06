import { describe, expect, test } from "bun:test";
import { arcPath } from "../abstract/monitors/svg/arc-path.js";
import { donutSvg } from "../abstract/monitors/svg/donut-svg.js";
import { durationLabel } from "../abstract/monitors/svg/duration-label.js";
import { ledSvg } from "../abstract/monitors/svg/led-svg.js";
import { ringSvg } from "../abstract/monitors/svg/ring-svg.js";
import { sparklineSvg } from "../abstract/monitors/svg/sparkline-svg.js";
import { levelCountsHtml } from "../components/all-monitors-page/level-counts-html.js";

describe("svg builders", () => {
  test("led escapes its title", () => {
    const svg = ledSvg("lightgreen", { title: "<x>" });
    expect(svg).toContain("&lt;x&gt;");
    expect(svg).toContain('fill="lightgreen"');
  });

  test("arc from 12 o'clock to 3 o'clock", () => {
    expect(arcPath(50, 50, 40, 0, Math.PI / 2)).toBe(
      "M 50.00 10.00 A 40 40 0 0 1 90.00 50.00",
    );
  });

  test("ring draws no arc at zero and labels the middle", () => {
    expect(ringSvg(0, "#f00", "0s")).not.toContain("<path");
    expect(ringSvg(0.5, "#f00", "30s")).toContain("<path");
    expect(ringSvg(0.5, "#f00", "30s")).toContain(">30s</text>");
  });

  test("donut has one arc per non-empty segment and shows the total", () => {
    const svg = donutSvg([
      { label: "up", value: 3, color: "#0f0" },
      { label: "down", value: 0, color: "#f00" },
      { label: "x", value: 1, color: "#00f" },
    ]);
    expect(svg.match(/<path/g)).toHaveLength(2);
    expect(svg).toContain(">4</text>");
  });

  test("sparkline needs two points for a line", () => {
    expect(sparklineSvg([5], "#00f")).not.toContain("polyline");
    expect(sparklineSvg([1, 2, 3], "#00f")).toContain("polyline");
  });

  test("durations and level tallies", () => {
    expect(durationLabel(75)).toBe("1m 15s");
    expect(durationLabel(7300)).toBe("2h 1m");
    expect(durationLabel(null)).toBe("—");
    expect(levelCountsHtml(["ok", "ok", "crit"])).toContain("2 OK");
  });
});
