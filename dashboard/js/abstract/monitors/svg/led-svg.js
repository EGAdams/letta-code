import { esc } from "./svg-escape.js";

/** A round LED with a soft highlight, filled with `color`. */
export function ledSvg(color, { size = 14, title = "" } = {}) {
  const r = size / 2;
  return (
    `<svg class="led" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(title)}">` +
    `<title>${esc(title)}</title>` +
    `<circle cx="${r}" cy="${r}" r="${r - 1}" fill="${esc(color)}" stroke="rgba(0,0,0,.35)" stroke-width="1"/>` +
    `<circle cx="${r * 0.7}" cy="${r * 0.7}" r="${r * 0.3}" fill="rgba(255,255,255,.6)"/>` +
    `</svg>`
  );
}
