function barClassFor(percent) {
  if (percent == null) return "";
  if (percent <= 10) return "is-critical";
  if (percent <= 30) return "is-low";
  return "";
}

export function buildAssignmentUsageBar(el) {
  const cell = el("td", { className: "win98-bar-cell" });
  const track = el("div", { className: "win98-bar-track" });
  const fill = el("div", { className: "win98-bar-fill" });
  const label = el("div", { className: "win98-bar-label" });
  track.append(fill, label);
  cell.appendChild(track);
  return { cell, fill, label };
}

export function renderAssignmentUsageBar(
  entry,
  row,
  { tokenAware = false } = {},
) {
  const percent = row.weekly_percent_remaining;
  const tokenDown = tokenAware && row.token_status === "down";
  const pending = percent == null && !tokenDown && row.token_reset_at;
  entry.fill.className = tokenDown
    ? "win98-bar-fill is-critical"
    : pending
      ? "win98-bar-fill is-pending"
      : `win98-bar-fill ${barClassFor(percent)}`.trim();
  entry.fill.style.width =
    tokenDown || pending
      ? "100%"
      : percent == null
        ? "0%"
        : `${Math.max(0, Math.min(100, percent))}%`;
  if (pending) {
    entry.label.innerHTML = `<span data-countdown-until="${row.token_reset_at}">…</span>`;
  } else if (tokenDown) {
    entry.label.textContent = row.token_status_detail || "Expired";
  } else if (percent == null && tokenAware && row.token_status === "up") {
    entry.label.textContent = "Valid";
  } else {
    entry.label.textContent = percent == null ? "Unavailable" : `${percent}%`;
  }
  entry.label.title = row.token_status_detail || "";
}
