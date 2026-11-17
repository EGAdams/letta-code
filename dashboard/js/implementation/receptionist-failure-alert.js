/**
 * ReceptionistFailureAlert — polls /api/receptionist-alerts (10s) and raises
 * one red card per task Toyota or Sydney sent through the post office that
 * FAILED: a plan Opus never wrote, a build Sonnet never ran, an errand the
 * mechanic never did. Those failures used to sit unread in a mailbox; this
 * puts them in front of the user on whatever tab is open.
 *
 * Each new alert is shown, spoken once (the same speech the receptionists use;
 * not gated by Pause, because Pause is for conversation, not alarms), and
 * raised as a browser Notification when permitted. "Got it" POSTs
 * /api/receptionist-alerts/ack so it stops reappearing; a card whose alert the
 * server no longer lists (heard on a turn, or acked elsewhere) is removed.
 * A receptionist that is up but cannot read her alerts gets a card too.
 *
 * Same injected http/doc/setInterval shape as IntakeHaltAlert, so it's
 * unit-testable without a browser.
 */
export class ReceptionistFailureAlert {
  constructor({
    http,
    doc = globalThis.document,
    speech = null,
    notify = defaultNotify(globalThis),
    storage = safeStorage(globalThis),
    intervalMs = 10000,
    setInterval: setIntervalFn = globalThis.setInterval?.bind(globalThis),
  } = {}) {
    if (!http)
      throw new Error("ReceptionistFailureAlert requires an HttpClient");
    this._http = http;
    this._doc = doc;
    this._speech = speech;
    this._notify = notify;
    this._storage = storage;
    this._intervalMs = intervalMs;
    this._setInterval = setIntervalFn;
    this._cards = new Map(); // key -> element
    this._container = null;
    this._bar = null;
    this._barLabel = null;
    this._hidden = new Set(); // unackable keys hidden on this page
  }

  start() {
    this.poll();
    if (this._setInterval)
      this._setInterval(() => this.poll(), this._intervalMs);
  }

  async poll() {
    let payload;
    try {
      payload = await this._http.getJSON("/api/receptionist-alerts");
    } catch {
      return; // the dashboard itself is down; nothing here can be shown
    }
    const live = new Map();
    for (const alert of payload?.alerts || []) {
      const key = alert.task_id
        ? `task:${alert.task_id}`
        : `${alert.agent}:${alert.id}`;
      const item = {
        agent: alert.agent,
        ids: [alert.id],
        title: alert.title || `${alert.name || alert.agent}: a task failed`,
        text: alert.spoken || alert.error || "A task failed.",
        severity: alert.severity || "notice",
      };
      const existing = live.get(key);
      if (existing) {
        existing.sources.push(item);
        if (severityRank(item.severity) > severityRank(existing.severity)) {
          existing.title = item.title;
          existing.text = item.text;
          existing.severity = item.severity;
        }
      } else {
        live.set(key, { ...item, sources: [item] });
      }
    }
    for (const err of payload?.errors || []) {
      live.set(`${err.agent}:unreadable`, {
        agent: err.agent,
        ids: null,
        title: `${err.name || err.agent} can't read her failure alerts`,
        text: err.error || "unknown error",
        ackable: false,
        sources: [],
      });
    }
    for (const [key, el] of this._cards) {
      if (!live.has(key)) {
        el.remove();
        this._cards.delete(key);
      }
    }
    for (const key of this._hidden)
      if (!live.has(key)) this._hidden.delete(key);
    for (const [key, alert] of live) {
      if (this._cards.has(key) || this._hidden.has(key)) continue;
      this._cards.set(key, this._card(key, alert));
      if (this._firstHearing(key)) this._announce(alert);
    }
    this._syncBar();
  }

  async acknowledge(key, alert) {
    try {
      for (const source of alert.sources || [alert])
        await this._http.postJSON("/api/receptionist-alerts/ack", {
          agent: source.agent,
          ids: source.ids,
        });
    } catch {
      // Best-effort: hide it locally; if the ack never landed, the next poll
      // brings it back, which is the point.
    }
    this._cards.get(key)?.remove();
    this._cards.delete(key);
    this._syncBar();
  }

  /**
   * True the first time this browser meets an alert. Every page load used to
   * re-speak every unacknowledged alert, so a phone reload with four pending
   * read all four aloud again; the card still shows, the voice doesn't repeat.
   */
  _firstHearing(key) {
    if (!this._storage) return true;
    let heard = [];
    try {
      heard = JSON.parse(this._storage.getItem(HEARD_KEY) || "[]");
      if (!Array.isArray(heard)) heard = [];
    } catch {
      heard = [];
    }
    if (heard.includes(key)) return false;
    heard.push(key);
    try {
      this._storage.setItem(HEARD_KEY, JSON.stringify(heard.slice(-200)));
    } catch {
      // storage full or blocked: speaking twice beats never speaking
    }
    return true;
  }

  _announce(alert) {
    try {
      this._speech?.speak?.(`${alert.title}. ${alert.text}`, alert.agent);
    } catch {
      // speech is a courtesy; the card is the record
    }
    try {
      this._notify?.(alert.title, alert.text);
    } catch {
      // ditto
    }
  }

  _box() {
    if (this._container && this._container.parent !== null)
      return this._container;
    const box = this._doc.createElement("div");
    box.id = "receptionist-failure-alerts";
    box.className = "receptionist-failure-alerts";
    // Phone-safe: never wider than the screen, never taller than it, and
    // scrollable inside itself, so every card's buttons can be reached even
    // when a dozen long alerts are stacked.
    Object.assign(box.style, {
      position: "fixed",
      top: "12px",
      right: "12px",
      zIndex: "10000",
      width: "min(420px, calc(100vw - 24px))",
      maxHeight: "calc(100vh - 24px)",
      overflowY: "auto",
      overscrollBehavior: "contain",
      WebkitOverflowScrolling: "touch",
      display: "flex",
      flexDirection: "column",
      gap: "8px",
    });
    // A later assignment the browser doesn't understand is ignored, so this
    // upgrades to the visible-viewport height where supported (mobile URL bar).
    box.style.maxHeight = "calc(100dvh - 24px)";
    this._doc.body.appendChild(box);
    this._container = box;
    return box;
  }

  /** "Dismiss all" bar, shown only while two or more cards are stacked. */
  _syncBar() {
    const box = this._box();
    const count = this._cards.size;
    if (count < 2) {
      this._bar?.remove();
      this._bar = null;
      return;
    }
    if (!this._bar) {
      const bar = this._doc.createElement("div");
      bar.className = "receptionist-failure-alerts-bar";
      Object.assign(bar.style, {
        position: "sticky",
        top: "0",
        zIndex: "1",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "8px",
        background: "#5c0010",
        color: "#fff",
        padding: "6px 8px 6px 12px",
        borderRadius: "6px",
        fontSize: "14px",
        boxShadow: "0 2px 8px rgba(0,0,0,.4)",
      });
      const label = this._doc.createElement("span");
      label.className = "receptionist-failure-alerts-count";
      const all = this._doc.createElement("button");
      all.type = "button";
      all.className = "receptionist-failure-alerts-dismiss-all";
      all.textContent = "Dismiss all";
      Object.assign(all.style, buttonStyle());
      all.addEventListener("click", () => this.dismissAll());
      bar.appendChild(label);
      bar.appendChild(all);
      this._bar = bar;
      this._barLabel = label;
      box.insertBefore(bar, box.children[0] || null);
    }
    this._barLabel.textContent = `${count} alerts`;
  }

  /** Acknowledge (or locally hide) every card at once. */
  async dismissAll() {
    for (const [key, el] of [...this._cards]) {
      const alert = el._alert;
      if (alert?.ackable === false) this._hide(key);
      else await this.acknowledge(key, alert);
    }
    this._syncBar();
  }

  /**
   * A card with nothing to acknowledge (a receptionist that can't read her
   * alerts) is hidden on this page only; it returns if the condition clears
   * and recurs, but not on every poll while it persists.
   */
  _hide(key) {
    this._hidden.add(key);
    this._cards.get(key)?.remove();
    this._cards.delete(key);
    this._syncBar();
  }

  _card(key, alert) {
    const card = this._doc.createElement("div");
    card.className = "receptionist-failure-alert";
    card.dataset.alertKey = key;
    card._alert = alert;
    Object.assign(card.style, {
      position: "relative",
      flex: "0 0 auto",
      background: "#b00020",
      color: "#fff",
      padding: "10px 48px 10px 12px",
      borderRadius: "6px",
      boxShadow: "0 2px 8px rgba(0,0,0,.4)",
      fontSize: "14px",
      lineHeight: "1.35",
      overflowWrap: "anywhere",
    });
    const title = this._doc.createElement("strong");
    title.textContent = alert.title;
    const text = this._doc.createElement("div");
    text.className = "receptionist-failure-alert-text";
    text.textContent = alert.text;
    const long = String(alert.text || "").length > LONG_TEXT;
    if (long) Object.assign(text.style, CLAMPED);
    card.appendChild(title);
    card.appendChild(text);
    if (alert.ackable !== false) {
      const ack = this._doc.createElement("button");
      ack.type = "button";
      ack.className = "receptionist-failure-alert-ack";
      ack.textContent = "Got it";
      Object.assign(ack.style, buttonStyle(), { marginTop: "8px" });
      ack.addEventListener("click", () => this.acknowledge(key, alert));
      card.appendChild(ack);
    }
    if (long) {
      const more = this._doc.createElement("button");
      more.type = "button";
      more.className = "receptionist-failure-alert-more";
      more.textContent = "Show more";
      Object.assign(more.style, buttonStyle(), {
        marginTop: "8px",
        marginLeft: "8px",
        background: "transparent",
        color: "#fff",
        border: "1px solid rgba(255,255,255,.7)",
      });
      let open = false;
      more.addEventListener("click", () => {
        open = !open;
        Object.assign(text.style, open ? UNCLAMPED : CLAMPED);
        more.textContent = open ? "Show less" : "Show more";
      });
      card.appendChild(more);
    }
    // The close button is pinned to the card's top-right corner, so it is
    // reachable without scrolling through a long message, and big enough to
    // hit with a thumb.
    const close = this._doc.createElement("button");
    close.type = "button";
    close.className = "receptionist-failure-alert-close";
    close.textContent = "\u00d7";
    close.setAttribute("aria-label", "Dismiss alert");
    Object.assign(close.style, {
      position: "absolute",
      top: "2px",
      right: "2px",
      width: "44px",
      height: "44px",
      border: "none",
      background: "transparent",
      color: "#fff",
      fontSize: "26px",
      lineHeight: "1",
      cursor: "pointer",
    });
    close.addEventListener("click", () =>
      alert.ackable === false ? this._hide(key) : this.acknowledge(key, alert),
    );
    card.appendChild(close);
    this._box().appendChild(card);
    return card;
  }
}

const HEARD_KEY = "receptionist-failure-alerts:heard";
const LONG_TEXT = 180;
const CLAMPED = {
  display: "-webkit-box",
  WebkitLineClamp: "4",
  WebkitBoxOrient: "vertical",
  overflow: "hidden",
};
const UNCLAMPED = {
  display: "block",
  WebkitLineClamp: "unset",
  WebkitBoxOrient: "unset",
  overflow: "visible",
};

function buttonStyle() {
  return {
    minHeight: "36px",
    padding: "6px 14px",
    border: "none",
    borderRadius: "4px",
    background: "#fff",
    color: "#b00020",
    fontWeight: "600",
    fontSize: "14px",
    cursor: "pointer",
  };
}

function severityRank(severity) {
  return { notice: 1, escalated: 2, urgent: 3 }[severity] || 0;
}

/** A browser Notification when the user has allowed them; asks once if not. */
function defaultNotify(win) {
  const N = win?.Notification;
  if (!N) return null;
  return (title, body) => {
    if (N.permission === "granted")
      new N(title, { body, requireInteraction: true });
    else if (N.permission === "default") N.requestPermission?.();
  };
}

/** localStorage, or null where it is missing or throws (private windows). */
function safeStorage(win) {
  try {
    const store = win?.localStorage;
    if (!store) return null;
    store.getItem(HEARD_KEY);
    return store;
  } catch {
    return null;
  }
}
