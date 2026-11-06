import { esc } from "./svg-escape.js";

/**
 * A sparkline of `values` (oldest first): a 2px line, a light area under it,
 * and a dot on the latest reading.
 */
export function sparklineSvg(
  values,
  color,
  { width = 220, height = 60, pad = 4 } = {},
) {
  const shown = values.filter(Number.isFinite);
  const frame = `<svg class="sparkline" viewBox="0 0 ${width} ${height}" width="100%" height="${height}" preserveAspectRatio="none" role="img" aria-label="trend">`;
  if (shown.length < 2) {
    return `${frame}<line x1="${pad}" x2="${width - pad}" y1="${height - pad}" y2="${height - pad}" stroke="var(--mon-track, #e9ecef)" stroke-width="2"/></svg>`;
  }
  const max = Math.max(...shown, 1);
  const x = (i) => pad + (i / (shown.length - 1)) * (width - pad * 2);
  const y = (v) => height - pad - (v / max) * (height - pad * 2);
  const points = shown.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  const last = shown.length - 1;
  return (
    frame +
    `<polygon points="${pad},${height - pad} ${points.join(" ")} ${x(last).toFixed(1)},${height - pad}" fill="${esc(color)}" opacity=".15"/>` +
    `<polyline points="${points.join(" ")}" fill="none" stroke="${esc(color)}" stroke-width="2" vector-effect="non-scaling-stroke"/>` +
    `<circle cx="${x(last).toFixed(1)}" cy="${y(shown[last]).toFixed(1)}" r="3" fill="${esc(color)}"/>` +
    `</svg>`
  );
}
