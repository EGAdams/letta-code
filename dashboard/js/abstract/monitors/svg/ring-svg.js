import { arcPath } from "./arc-path.js";
import { esc } from "./svg-escape.js";

/** A countdown ring: the coloured arc is the fraction of the wait remaining. */
export function ringSvg(
  fraction,
  color,
  label,
  { size = 120, stroke = 10 } = {},
) {
  const c = size / 2;
  const r = c - stroke / 2 - 1;
  const f = Number.isFinite(fraction) ? Math.min(1, Math.max(0, fraction)) : 0;
  const arc =
    f > 0
      ? `<path d="${arcPath(c, c, r, 0, f * Math.PI * 2)}" fill="none" stroke="${esc(color)}" stroke-width="${stroke}" stroke-linecap="round"/>`
      : "";
  return (
    `<svg class="ring" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img" aria-label="${esc(label)}">` +
    `<circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="var(--mon-track, #e9ecef)" stroke-width="${stroke}"/>` +
    arc +
    `<text x="${c}" y="${c}" text-anchor="middle" dominant-baseline="central" class="ring-label">${esc(label)}</text>` +
    `</svg>`
  );
}
