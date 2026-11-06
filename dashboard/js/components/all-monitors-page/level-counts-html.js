import { levelLed } from "../../abstract/monitors/levels/level-palette.js";
import { LEVELS } from "../../abstract/monitors/levels/level-rank.js";
import { ledSvg } from "../../abstract/monitors/svg/led-svg.js";

const NAMES = {
  ok: "OK",
  unknown: "No data",
  warn: "Warning",
  crit: "Critical",
};

/** "● 18 OK  ● 2 Warning …" — the page header's tally, worst last. */
export function levelCountsHtml(levels) {
  return LEVELS.map((level) => {
    const n = levels.filter((l) => l === level).length;
    return n
      ? `<span class="count ${level}">${ledSvg(levelLed(level), { size: 12, title: NAMES[level] })} ${n} ${NAMES[level]}</span>`
      : "";
  }).join("");
}
