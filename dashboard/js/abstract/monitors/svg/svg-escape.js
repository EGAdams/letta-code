/** Escapes text for SVG/HTML markup. */
const MAP = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => MAP[c]);
}
