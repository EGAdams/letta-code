// pc-metrics-render.js — pure HTML builder for a PC Monitor card.
//
// Issue detection: each metric carries level ok|warn|crit — warn blinks the
// PC's tab yellow (the existing .tab-alert animation), crit blinks it red
// (.tab-alert-red). Disk levels come from GB free on the Windows C: drive
// (yellow under 5 GB, red at 2 GB or less). Thresholds live in server.py
// (PC_ALERT_THRESHOLDS, env-tunable) — no frontend change.

import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;

export function renderPcMetrics(d) {
  if (!d || d.ok === false) {
    return `<p class="am-warn">${esc(d?.error || "no data")}</p>`;
  }
  let h = '<div class="ms-card">';
  const flag =
    d.level === "crit"
      ? ' <span class="pcm-crit-flag">⚠ critical</span>'
      : d.alert
        ? ' <span class="pcm-alert-flag">⚠ needs attention</span>'
        : "";
  h += `<h3>${esc(d.label)}${flag}</h3>`;
  if (d.note) h += `<p class="am-dim">${esc(d.note)}</p>`;
  if (d.stale) {
    h += `<p class="am-warn">⚠ live sample failed — showing last good reading (${esc(d.stale_error || "")})</p>`;
  }
  for (const m of d.metrics || []) {
    const pct = Math.max(0, Math.min(100, m.percent || 0));
    const fill =
      m.level === "crit"
        ? "#e53935"
        : m.alert
          ? "#f9a825"
          : pct >= 75
            ? "#fb8c00"
            : "#43a047";
    const blink = m.alert ? " ms-blink-warn" : "";
    h += `<div class="ms-window" title="${esc(m.tip || "")}"><div class="ms-window-head"><span>${esc(m.label)}</span><span>${esc(m.text || "")} · ${pct}%${m.alert ? " ⚠" : ""}</span></div>`;
    h += `<div class="ms-bar"><div class="ms-bar-fill${blink}" style="width:${pct}%;background:${fill}"></div></div></div>`;
  }
  if (d.as_of) {
    h += `<p class="am-dim">as of ${new Date(d.as_of * 1000).toLocaleTimeString()}</p>`;
  }
  h += "</div>";
  return h;
}
