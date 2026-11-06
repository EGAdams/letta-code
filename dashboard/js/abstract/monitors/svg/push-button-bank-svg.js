import { chromeKeySvg, KEY_PITCH } from "./chrome-key-svg.js";
import { esc } from "./svg-escape.js";

const DEFS =
  `<defs>` +
  `<linearGradient id="chrome" x1="0" y1="0" x2="0" y2="1">` +
  `<stop offset="0" stop-color="#ffffff"/><stop offset=".38" stop-color="#cfd4d9"/>` +
  `<stop offset=".5" stop-color="#7b838b"/><stop offset=".56" stop-color="#eef1f3"/>` +
  `<stop offset="1" stop-color="#a3aab1"/></linearGradient>` +
  `<linearGradient id="chrome-in" x1="0" y1="0" x2="0" y2="1">` +
  `<stop offset="0" stop-color="#8d949a"/><stop offset=".45" stop-color="#5d646b"/>` +
  `<stop offset=".55" stop-color="#b3b9bf"/><stop offset="1" stop-color="#6c737a"/></linearGradient>` +
  `<linearGradient id="slot-shadow" x1="0" y1="0" x2="0" y2="1">` +
  `<stop offset="0" stop-color="#000" stop-opacity=".85"/><stop offset=".35" stop-color="#000" stop-opacity=".25"/>` +
  `<stop offset="1" stop-color="#000" stop-opacity="0"/></linearGradient>` +
  `<linearGradient id="plate" x1="0" y1="0" x2="0" y2="1">` +
  `<stop offset="0" stop-color="#3a3530"/><stop offset="1" stop-color="#16130f"/></linearGradient>` +
  `</defs>`;

/** A row of chrome push buttons on a dark plate: an SVG radio group. */
export function pushButtonBankSvg(presets, selected, title = "Gauge shows") {
  const width = presets.length * KEY_PITCH + 6;
  const keys = presets
    .map((p, i) => chromeKeySvg(p, 6 + i * KEY_PITCH, p.key === selected))
    .join("");
  return (
    `<svg class="bank" viewBox="0 0 ${width} 44" role="radiogroup" aria-label="${esc(title)}">` +
    DEFS +
    `<rect class="plate" x="0" y="0" width="${width}" height="44" rx="6"/>` +
    keys +
    `</svg>`
  );
}
