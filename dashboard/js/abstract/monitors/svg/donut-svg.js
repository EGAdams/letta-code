import { arcPath } from "./arc-path.js";
import { esc } from "./svg-escape.js";

/**
 * A donut of {label, value, color} segments with the total in the middle.
 * Each segment carries a <title> so hovering names it.
 */
export function donutSvg(
  segments,
  { size = 120, stroke = 16, center = null } = {},
) {
  const c = size / 2;
  const r = c - stroke / 2 - 1;
  const total = segments.reduce(
    (sum, s) => sum + (s.value > 0 ? s.value : 0),
    0,
  );
  let angle = 0;
  const gap = segments.length > 1 ? 0.03 : 0;
  const arcs = segments
    .filter((s) => s.value > 0)
    .map((s) => {
      const sweep = (s.value / total) * Math.PI * 2;
      const path = arcPath(c, c, r, angle + gap / 2, angle + sweep - gap / 2);
      angle += sweep;
      return `<path d="${path}" fill="none" stroke="${esc(s.color)}" stroke-width="${stroke}"><title>${esc(s.label)}: ${s.value}</title></path>`;
    });
  return (
    `<svg class="donut" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img" aria-label="${esc(segments.map((s) => `${s.label} ${s.value}`).join(", "))}">` +
    `<circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="var(--mon-track, #e9ecef)" stroke-width="${stroke}"/>` +
    arcs.join("") +
    `<text x="${c}" y="${c}" text-anchor="middle" dominant-baseline="central" class="donut-total">${esc(center ?? total)}</text>` +
    `</svg>`
  );
}
