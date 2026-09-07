import { PollingController } from "../abstract/polling-controller.interface.js";

/**
 * Full-scale of the meter, in tokens per minute.
 *
 * There is no provider-published token ceiling to scale against the way
 * Model Stats scales against a quota window, so this is a declared reading
 * scale rather than a limit: one SDK run costs 20k-60k tokens including cache
 * reads, so 100k/min is "several runs a minute, sustained" — heavy, and worth
 * the bar turning red before it pins.
 */
export const RATE_BAR_FULL_SCALE = 100000;

/** Above this fraction of full scale the meter reads as hot. */
export const RATE_BAR_HOT_FRACTION = 0.6;

/** 850 -> "850", 8400 -> "8.4k", 1_240_000 -> "1.2M". */
export function formatTokens(value) {
  const n = Number(value) || 0;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(Math.round(n));
}

/** The window the headline reads from: short enough to be live, long enough
 *  not to swing wildly on a single run finishing. */
export function primaryWindow(windows) {
  const list = Array.isArray(windows) ? windows : [];
  return list.find((w) => w.seconds === 300) || list[0] || null;
}

export function currentRunText(run) {
  if (!run) return "";
  const tokens = formatTokens(run.total_tokens);
  if (run.status === "running") {
    return `${run.model || "Claude"} running now — ${tokens} so far`;
  }
  return `last run (${run.model || "Claude"}): ${tokens} tokens`;
}

export function historyNote(payload) {
  const count = Number(payload?.sample_count) || 0;
  if (!count) {
    return "No finished SDK runs recorded yet — the rate starts at the next one.";
  }
  const since = Number(payload?.observed_since) || 0;
  const when = since
    ? new Date(since * 1000).toLocaleString()
    : "an unknown time";
  return `${count} finished run${count === 1 ? "" : "s"} recorded since ${when}. Windows still filling are shown greyed.`;
}

/**
 * Renders the Claude Code SDK token-rate strip on Server Management.
 *
 * Deliberately a second controller rather than more branches inside
 * ClaudeSdkActivityController: that one narrates a run in progress at 1Hz,
 * this one reports an accumulated rate and has nothing to say between runs,
 * so they poll different endpoints at different cadences.
 */
export class ClaudeSdkTokenRateController extends PollingController {
  constructor({ http, doc = document, ...opts } = {}) {
    super({ intervalMs: 5000, ...opts });
    if (!http) throw new Error("ClaudeSdkTokenRateController requires http");
    this._http = http;
    this._doc = doc;
    this._primary = doc.getElementById("claude-sdk-rate-primary");
    this._current = doc.getElementById("claude-sdk-rate-current");
    this._fill = doc.getElementById("claude-sdk-rate-fill");
    this._windows = doc.getElementById("claude-sdk-rate-windows");
    this._note = doc.getElementById("claude-sdk-rate-note");
  }

  async poll() {
    let payload;
    try {
      payload = await this._http.getJSON("/api/claude-sdk-token-rate");
    } catch (error) {
      this._showUnavailable(error.message);
      return;
    }
    if (!payload || typeof payload !== "object") {
      this._showUnavailable("empty token-rate response");
      return;
    }
    this._render(payload);
  }

  _showUnavailable(detail) {
    if (this._primary) {
      this._primary.textContent = "unavailable";
      this._primary.className = "claude-sdk-rate-primary is-error";
    }
    if (this._note) this._note.textContent = `Token rate — ${detail}`;
  }

  _render(payload) {
    const windows = Array.isArray(payload.windows) ? payload.windows : [];
    const lead = primaryWindow(windows);
    const rate = Number(lead?.tokens_per_minute) || 0;

    if (this._primary) {
      this._primary.textContent = `${formatTokens(rate)} tok/min`;
      this._primary.className = `claude-sdk-rate-primary${rate ? "" : " is-idle"}`;
    }
    if (this._current) {
      this._current.textContent = currentRunText(payload.current_run);
    }
    if (this._fill) {
      const fraction = Math.min(1, rate / RATE_BAR_FULL_SCALE);
      this._fill.style.width = `${(fraction * 100).toFixed(1)}%`;
      this._fill.classList.toggle("is-hot", fraction >= RATE_BAR_HOT_FRACTION);
    }
    this._renderWindows(windows);
    if (this._note) {
      const trouble =
        payload.ok === false && payload.error ? ` ${payload.error}` : "";
      this._note.textContent = `${historyNote(payload)}${trouble}`;
    }
  }

  _renderWindows(windows) {
    if (!this._windows) return;
    this._windows.innerHTML = "";
    const doc = this._windows.ownerDocument || this._doc;
    for (const window of windows) {
      const cell = doc.createElement("div");
      cell.className = `claude-sdk-rate-window${window.complete ? "" : " is-partial"}`;
      const value = doc.createElement("b");
      value.textContent = `${formatTokens(window.tokens_per_minute)} tok/min`;
      const caption = doc.createElement("span");
      const runs = Number(window.runs) || 0;
      caption.textContent = `${window.label} — ${formatTokens(window.total_tokens)} in ${runs} run${runs === 1 ? "" : "s"}`;
      cell.append(value, caption);
      this._windows.appendChild(cell);
    }
  }
}
