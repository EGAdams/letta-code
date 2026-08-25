// model-stats-render.js — pure HTML builders for the Model Stats cards.
//
// No DOM, no fetch: given a /api/model-stats payload these return a string,
// so the formatting rules (which colour at which percentage, what a rate-limit
// banner says) are unit-testable without a browser.

import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;

/* The Rate of Change row. `rate` comes straight from /api/model-stats:
   pct_per_hour (raw %-points/hour), burn_multiple (vs the window's replenish
   pace — 1.0× is sustainable forever), bar_percent (pre-scaled so 50% width
   = 1.0×), warn (burn ≥ server threshold → blink). While history is still
   too short the server sends {available:false, reason} and we show that
   instead of a misleading empty bar. */
export function renderRateOfChange(rate) {
  if (!rate) return "";
  const tip =
    `Consumed ${rate.pct_per_hour ?? "?"}% of the ${rate.window_label || "quota"} limit per hour ` +
    `over the last ${rate.window_minutes || 30} min. 1.0× pace means the window refills as fast as ` +
    `you spend; sustained use above 1.0× eventually maxes out. Blinks yellow at ${rate.warn_at_multiple}×.`;
  let h = `<div class="ms-window" title="${esc(tip)}"><div class="ms-window-head"><span>Rate of change</span>`;
  if (!rate.available) {
    h += `<span class="am-dim">${esc(rate.reason || "gathering data…")}</span></div>`;
    h +=
      '<div class="ms-bar"><div class="ms-bar-fill" style="width:0%"></div></div></div>';
    return h;
  }
  const rp = Math.max(0, Math.min(100, rate.bar_percent || 0));
  const fill = rate.warn ? "#f9a825" : "#43a047";
  const blink = rate.warn ? " ms-blink-warn" : "";
  h += `<span>${rate.pct_per_hour}%/hr · ${rate.burn_multiple}× pace${rate.warn ? " ⚠" : ""}</span></div>`;
  h += `<div class="ms-bar"><div class="ms-bar-fill${blink}" style="width:${rp}%;background:${fill}"></div></div></div>`;
  return h;
}

/* Live reset countdown. renderModelStats stamps spans with
   data-countdown-until (unix seconds); one shared ticker keeps them counting
   down each second and re-fetches the card once a deadline passes so the tab
   flips back to green on its own. */
export function resetEpoch(when) {
  if (!when) return null;
  if (typeof when === "number") return when;
  const t = Date.parse(when);
  return Number.isNaN(t) ? null : t / 1000;
}

export function fmtCountdown(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}

export function renderModelStats(d) {
  if (!d || d.ok === false) {
    return `<p class="am-warn">${esc(d?.error || "no data")}</p>`;
  }
  const dot =
    d.status === "down"
      ? "#e53935"
      : d.status === "concern"
        ? "#f9a825"
        : "#43a047";
  let h = '<div class="ms-card">';
  h += `<h3>${esc(d.label)} <span style="color:${dot}">●</span></h3>`;
  h += `<button type="button" class="am-btn ms-mute-btn" data-mute-source="${esc(d.key)}" data-muted="${d.muted ? "1" : "0"}">${d.muted ? "Unmute warning" : "Mute warning"}</button>`;
  if (d.muted) {
    h += `<p class="am-dim">Warning silenced — actual status: ${esc(d.raw_status || d.status)}. Click Unmute once this is resolved.</p>`;
  }
  if (d.rate_limited) {
    // Provider-side 429: say so loudly, with the local reset time and a live
    // countdown — the whole point is never having to diagnose this from a
    // terminal again.
    const until = Number(d.rate_limited_until) || null;
    const at = until
      ? new Date(until * 1000).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      : null;
    h += `<p class="am-warn ms-rate-limited">⛔ RATE LIMITED (HTTP 429)${
      at
        ? ` — resets at ${at} · <span data-countdown-until="${until}">…</span>`
        : " — reset time not reported"
    }</p>`;
  }
  if (d.model) h += `<p><b>Model:</b> <code>${esc(d.model)}</code></p>`;
  if (d.detail) h += `<p class="am-dim">${esc(d.detail)}</p>`;
  if (d.windows_stale) {
    const sampled = d.usage_as_of
      ? new Date(d.usage_as_of * 1000).toLocaleString()
      : "the last successful check";
    h += `<p class="am-warn">Quota bars show the last successful reading (${esc(sampled)}) while live usage reporting is throttled.</p>`;
  }
  for (const w of d.windows || []) {
    if (w.unavailable) {
      h += `<div class="ms-window"><div class="ms-window-head"><span>${esc(w.label)}</span><span class="am-dim">${esc(w.note || "not reported")}</span></div></div>`;
      continue;
    }
    const pct = Math.max(0, Math.min(100, w.used_percent || 0));
    const bar = pct >= 100 ? "#e53935" : pct >= 80 ? "#f9a825" : "#43a047";
    const resets = w.resets_in ? ` · resets ${esc(w.resets_in)}` : "";
    h += `<div class="ms-window"><div class="ms-window-head"><span>${esc(w.label)}</span><span>${pct}%${resets}</span></div>`;
    h += `<div class="ms-bar"><div class="ms-bar-fill" style="width:${pct}%;background:${bar}"></div></div></div>`;
  }
  /* Rate of Change — server-computed burn rate of the primary quota window
     (%-points/hour vs the window's replenish pace; see server.py's
     "Model usage" section for the math). Half a bar = sustainable 1.0× pace;
     the fill blinks yellow when burn ≥ the server's warn threshold
     (MODEL_RATE_WARN_BURN_MULTIPLE). */
  h += renderRateOfChange(d.rate);
  if (d.leak?.suspected) {
    h += `<p class="ms-leak" title="Usage kept climbing across several consecutive time buckets even though the short-term rate looks calm — the signature of a background drip (leaked poller, stuck loop) rather than a normal work burst.">⚠ ${esc(d.leak.text || "Slow token drain")}</p>`;
  }
  if (d.status === "down" && !d.rate_limited) {
    // Show the reset of the window that's actually maxed (highest used %), not
    // just the first one — e.g. weekly at 100% while the 5-hour just reset.
    const maxed = (d.windows || [])
      .filter((w) => w.resets_in)
      .sort((a, b) => (b.used_percent || 0) - (a.used_percent || 0))[0];
    const maxedEpoch = resetEpoch(maxed?.resets_at);
    h += `<p class="am-warn">MAXED OUT${maxed ? ` — ${esc(maxed.label)} resets ${esc(maxed.resets_in)}` : ""}${maxedEpoch ? ` · <span data-countdown-until="${maxedEpoch}">…</span>` : ""}</p>`;
  }
  if (typeof d.tokens_used === "number") {
    h += `<p><b>Tokens used:</b> ${d.tokens_used.toLocaleString()}${d.cost_usd ? ` · $${d.cost_usd}` : ""}</p>`;
  }
  if (d.as_of) {
    h += `<p class="am-dim">as of ${new Date(d.as_of * 1000).toLocaleString()}</p>`;
  }
  h += "</div>";
  return h;
}
