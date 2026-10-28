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
    intervalMs = 10000,
    setInterval: setIntervalFn = globalThis.setInterval?.bind(globalThis),
  } = {}) {
    if (!http)
      throw new Error("ReceptionistFailureAlert requires an HttpClient");
    this._http = http;
    this._doc = doc;
    this._speech = speech;
    this._notify = notify;
    this._intervalMs = intervalMs;
    this._setInterval = setIntervalFn;
    this._cards = new Map(); // key -> element
    this._container = null;
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
      live.set(`${alert.agent}:${alert.id}`, {
        agent: alert.agent,
        ids: [alert.id],
        title: `${alert.name || alert.agent}: a task failed`,
        text: alert.spoken || alert.error || "A task failed.",
      });
    }
    for (const err of payload?.errors || []) {
      live.set(`${err.agent}:unreadable`, {
        agent: err.agent,
        ids: null,
        title: `${err.name || err.agent} can't read her failure alerts`,
        text: err.error || "unknown error",
        ackable: false,
      });
    }
    for (const [key, el] of this._cards) {
      if (!live.has(key)) {
        el.remove();
        this._cards.delete(key);
      }
    }
    for (const [key, alert] of live) {
      if (this._cards.has(key)) continue;
      this._cards.set(key, this._card(key, alert));
      this._announce(alert);
    }
  }

  async acknowledge(key, alert) {
    try {
      await this._http.postJSON("/api/receptionist-alerts/ack", {
        agent: alert.agent,
        ids: alert.ids,
      });
    } catch {
      // Best-effort: hide it locally; if the ack never landed, the next poll
      // brings it back, which is the point.
    }
    this._cards.get(key)?.remove();
    this._cards.delete(key);
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
    Object.assign(box.style, {
      position: "fixed",
      top: "12px",
      right: "12px",
      zIndex: "10000",
      maxWidth: "420px",
      display: "flex",
      flexDirection: "column",
      gap: "8px",
    });
    this._doc.body.appendChild(box);
    this._container = box;
    return box;
  }

  _card(key, alert) {
    const card = this._doc.createElement("div");
    card.className = "receptionist-failure-alert";
    card.dataset.alertKey = key;
    Object.assign(card.style, {
      background: "#b00020",
      color: "#fff",
      padding: "10px 12px",
      borderRadius: "6px",
      boxShadow: "0 2px 8px rgba(0,0,0,.4)",
      fontSize: "14px",
      lineHeight: "1.35",
    });
    const title = this._doc.createElement("strong");
    title.textContent = alert.title;
    const text = this._doc.createElement("div");
    text.className = "receptionist-failure-alert-text";
    text.textContent = alert.text;
    card.appendChild(title);
    card.appendChild(text);
    if (alert.ackable !== false) {
      const ack = this._doc.createElement("button");
      ack.type = "button";
      ack.className = "receptionist-failure-alert-ack";
      ack.textContent = "Got it";
      ack.addEventListener("click", () => this.acknowledge(key, alert));
      card.appendChild(ack);
    }
    this._box().appendChild(card);
    return card;
  }
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
