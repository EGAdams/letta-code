/**
 * SVG arc path from angle a0 to a1 (radians, 0 = 12 o'clock, clockwise)
 * on a circle of radius r centred at (cx, cy).
 */
export function arcPath(cx, cy, r, a0, a1) {
  const span = Math.min(a1 - a0, Math.PI * 2 - 1e-4);
  const end = a0 + span;
  const x0 = cx + r * Math.sin(a0);
  const y0 = cy - r * Math.cos(a0);
  const x1 = cx + r * Math.sin(end);
  const y1 = cy - r * Math.cos(end);
  const large = span > Math.PI ? 1 : 0;
  const f = (n) => n.toFixed(2);
  return `M ${f(x0)} ${f(y0)} A ${r} ${r} 0 ${large} 1 ${f(x1)} ${f(y1)}`;
}
