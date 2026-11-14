// dom-terminal-feed.js — System Status > Terminal, and an independent reader
// of /api/worker-activity (the same ledger Worker Activity reads; this view
// never writes anything or shares state with that page's own poller).
//
// One setTimeout chain, never two requests in flight: 5s while the Terminal
// view is active and the tab is visible, 20s otherwise, and a growing backoff
// (capped at 60s) while the endpoint is erroring — the connection keeps
// retrying on its own, with no page reload. Every line already produced by
// buildTerminalEvents() is appended at most once (exact text match), so a
// re-fetch of an unchanged ledger adds nothing. Clear empties only what is on
// screen: the dedupe set is left alone, so a cleared line already reported by
// the backend does not reappear just because the backend still reports it.
import { buildTerminalEvents } from "../abstract/terminal-feed.js";

const URL = "/api/worker-activity";
const FAST_MS = 5000;
const SLOW_MS = 20000;
const ERROR_STEP_MS = 15000;
const ERROR_MAX_MS = 60000;
const MAX_LINES = 2000;
const BOTTOM_TOLERANCE_PX = 8;

export function createTerminalFeed({ doc = document, win = window, http }) {
  const view = doc.getElementById("terminal");
  const stream = doc.getElementById("terminal-stream");
  const status = doc.getElementById("terminal-status");
  const clearButton = doc.getElementById("terminal-clear");

  const seen = new Set();
  const order = [];
  const state = {
    follow: true,
    timer: null,
    inflight: null,
    started: true,
    consecutiveErrors: 0,
    clearEpoch: null,
    baselinePending: false,
    suppressed: new Set(),
  };

  function isAtBottom() {
    if (!stream) return true;
    return (
      stream.scrollHeight - stream.scrollTop - stream.clientHeight <=
      BOTTOM_TOLERANCE_PX
    );
  }

  function bindScroll() {
    if (!stream || stream._terminalFeedScrollBound) return;
    stream._terminalFeedScrollBound = true;
    stream.addEventListener?.("scroll", () => {
      state.follow = isAtBottom();
    });
  }

  function append(text) {
    if (!stream || seen.has(text) || state.suppressed.has(text)) return;
    seen.add(text);
    const node = doc.createElement("div");
    node.className = text.includes("[gap:")
      ? "terminal-line terminal-line-gap"
      : "terminal-line";
    node.textContent = text;
    stream.appendChild(node);
    order.push(node);
    while (order.length > MAX_LINES) {
      const oldest = order.shift();
      seen.delete(oldest?.textContent);
      oldest?.remove?.();
    }
  }

  function pruneTaskLines(events) {
    const visibleTaskIds = new Set(
      events
        .map((text) => text.match(/\[task:([^\s\]]+)\s+agent:/)?.[1])
        .filter(Boolean),
    );
    for (const node of [...order]) {
      const taskId = node.textContent.match(/\[task:([^\s\]]+)\s+agent:/)?.[1];
      if (taskId && !visibleTaskIds.has(taskId)) {
        seen.delete(node.textContent);
        node.remove?.();
        const index = order.indexOf(node);
        if (index >= 0) order.splice(index, 1);
      }
    }
  }

  function clearVisible() {
    const current = [...seen];
    if (stream) stream.textContent = "";
    order.length = 0;
    seen.clear();
    state.baselinePending = true;
    state.suppressed = new Set(current);
    state.follow = true;
  }

  function isActive() {
    return view ? !!view.classList?.contains("active") : true;
  }

  function setStatus(text, level) {
    if (!status) return;
    status.textContent = text;
    status.className = level
      ? `terminal-status terminal-status-${level}`
      : "terminal-status";
  }

  function nextIntervalMs() {
    if (state.consecutiveErrors > 0) {
      return Math.min(ERROR_STEP_MS * state.consecutiveErrors, ERROR_MAX_MS);
    }
    const hidden = doc.visibilityState === "hidden";
    return isActive() && !hidden ? FAST_MS : SLOW_MS;
  }

  function schedule() {
    win.clearTimeout(state.timer);
    if (!state.started) return;
    state.timer = win.setTimeout(() => void poll(), nextIntervalMs());
  }

  function poll() {
    // A stopped feed can be explicitly reactivated through the public poll
    // method (for example when its view is mounted again).
    state.started = true;
    if (state.inflight) return state.inflight;
    state.inflight = (async () => {
      let payload;
      try {
        payload = await http.getJSON(URL);
      } catch (error) {
        state.consecutiveErrors += 1;
        setStatus(
          `Reconnecting — ${error.message || "request failed"} (attempt ${state.consecutiveErrors})`,
          "error",
        );
        return;
      }
      if (!state.started) return;
      state.consecutiveErrors = 0;
      bindScroll();
      const epoch = payload?.terminal_clear_epoch ?? 0;
      if (state.clearEpoch !== null && epoch !== state.clearEpoch)
        clearVisible();
      if (state.clearEpoch === null && epoch > 0) state.baselinePending = true;
      state.clearEpoch = epoch;
      const wasFollowing = state.follow;
      const events = buildTerminalEvents(payload);
      if (state.baselinePending) {
        state.suppressed = new Set(events);
        state.baselinePending = false;
      } else {
        pruneTaskLines(events);
        for (const text of events) append(text);
      }
      if (stream && wasFollowing) stream.scrollTop = stream.scrollHeight;
      setStatus(
        `Connected — last update ${new Date().toLocaleTimeString()}`,
        "ok",
      );
    })().finally(() => {
      state.inflight = null;
      schedule();
    });
    return state.inflight;
  }

  function clear() {
    clearVisible();
    void http.postJSON?.("/api/terminal-clear", {}).catch?.(() => {});
  }

  clearButton?.addEventListener?.("click", clear);
  doc.addEventListener?.("visibilitychange", () => {
    if (doc.visibilityState === "visible" && isActive()) void poll();
  });

  void poll();

  return {
    poll,
    clear,
    stop() {
      state.started = false;
      win.clearTimeout(state.timer);
      state.timer = null;
    },
  };
}
