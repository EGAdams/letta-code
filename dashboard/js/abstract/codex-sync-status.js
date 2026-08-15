/**
 * Codex sync status — shape guard + pure rendering, no DOM/fetch.
 *
 * The server's Pydantic StrictModel (codex_sync_status.CodexSyncStatus)
 * guards this shape on the way out; `assertCodexSyncStatus` is the mirror
 * guard on the way in, since a plain fetch response carries no compile-time
 * type in vanilla JS. Fail loud on a malformed payload rather than render a
 * silently-wrong countdown.
 */

const REQUIRED_SLOT_FIELDS = { key: "string", label: "string" };

/**
 * @param {any} slot
 * @returns {{key:string, label:string, email:string|null}}
 */
export function assertCodexTokenSlot(slot) {
  if (!slot || typeof slot !== "object") {
    throw new TypeError(`CodexTokenSlot: expected object, got ${typeof slot}`);
  }
  for (const [field, type] of Object.entries(REQUIRED_SLOT_FIELDS)) {
    if (typeof slot[field] !== type) {
      throw new TypeError(
        `CodexTokenSlot.${field}: expected ${type}, got ${typeof slot[field]}`,
      );
    }
  }
  if (slot.email != null && typeof slot.email !== "string") {
    throw new TypeError(
      `CodexTokenSlot.email: expected string|null, got ${typeof slot.email}`,
    );
  }
  return { key: slot.key, label: slot.label, email: slot.email ?? null };
}

/**
 * Validate the /api/codex-sync-status|codex-sync-now payload shape.
 * @param {any} status
 * @returns {{interval_seconds:number, seconds_remaining:number|null,
 *            slots:Array<{key:string,label:string,email:string|null}>,
 *            ran:boolean, ok:boolean|null, output:string|null}}
 */
export function assertCodexSyncStatus(status) {
  if (!status || typeof status !== "object") {
    throw new TypeError(
      `CodexSyncStatus: expected object, got ${typeof status}`,
    );
  }
  if (typeof status.interval_seconds !== "number") {
    throw new TypeError(
      `CodexSyncStatus.interval_seconds: expected number, got ${typeof status.interval_seconds}`,
    );
  }
  if (
    status.seconds_remaining != null &&
    typeof status.seconds_remaining !== "number"
  ) {
    throw new TypeError(
      `CodexSyncStatus.seconds_remaining: expected number|null, got ${typeof status.seconds_remaining}`,
    );
  }
  if (!Array.isArray(status.slots)) {
    throw new TypeError(
      `CodexSyncStatus.slots: expected array, got ${typeof status.slots}`,
    );
  }
  return {
    interval_seconds: status.interval_seconds,
    seconds_remaining: status.seconds_remaining ?? null,
    slots: status.slots.map(assertCodexTokenSlot),
    ran: Boolean(status.ran),
    ok: status.ok ?? null,
    output: status.output ?? null,
    source: status.source ?? null,
    sync_enabled: status.sync_enabled !== false,
    toggle_error: status.toggle_error ?? null,
  };
}

export function escHtml(s) {
  return String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}

export function fmtRemaining(secs) {
  const clamped = Math.max(0, Math.round(secs));
  const h = Math.floor(clamped / 3600);
  const m = Math.floor((clamped % 3600) / 60);
  const s = clamped % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return `${h}:${mm}:${ss} until next auto-sync`;
}

/**
 * Pure render: validated status → panel HTML. Progress bar runs from full
 * (interval_seconds, just synced) down to empty (due now).
 * @param {any} rawStatus
 * @returns {string}
 */
export function renderCodexSyncPanel(rawStatus) {
  if (!rawStatus) {
    return '<div class="cs-panel"><p class="am-dim">codex sync: no data</p></div>';
  }
  let status;
  try {
    status = assertCodexSyncStatus(rawStatus);
  } catch (e) {
    return `<div class="cs-panel"><p class="am-warn">codex sync: bad status payload — ${escHtml(e.message)}</p></div>`;
  }

  const intervalS = status.interval_seconds || 0;
  const remainingS = status.seconds_remaining ?? intervalS;
  const pct =
    intervalS > 0
      ? Math.max(0, Math.min(100, (remainingS / intervalS) * 100))
      : 0;

  let h = '<div class="cs-panel">';
  h += '<div class="cs-panel-toolbar">';
  h += "<h4>Codex fallback token sync</h4>";
  h += `<button type="button" class="cs-toggle-btn" id="cs-toggle-sync-btn">${status.sync_enabled ? "Disable Sync" : "Enable Sync"}</button>`;
  h += "</div>";

  const bodyClass = status.sync_enabled
    ? "cs-panel-body"
    : "cs-panel-body cs-panel-body-disabled";
  h += `<div class="${bodyClass}">`;
  h += '<div class="cs-panel-head">';
  h += `<span id="cs-countdown-label" data-cs-countdown-remaining="${remainingS}" data-cs-countdown-interval="${intervalS}">…</span>`;
  h += "</div>";
  h += `<div class="ms-bar"><div class="ms-bar-fill" id="cs-swap-bar" style="width:${pct}%;background:#43a047"></div></div>`;
  h += '<div class="cs-panel-actions">';
  h +=
    '<button type="button" class="cs-swap-btn" id="cs-swap-r46-btn" title="Pull mom\'s R46 account into the fallback slot — keeps primary and fallback on different accounts">Sync from R46 (mom)</button>';
  h +=
    '<button type="button" class="cs-swap-btn cs-swap-btn-danger" id="cs-swap-w11-btn" title="Copy your own W11 account into the fallback slot — both slots become the same account, so this removes the dual-account failover on purpose">Copy from W11 (mine)</button>';
  h += "</div>";

  h += '<div class="cs-rows">';
  for (const slot of status.slots) {
    h += '<div class="cs-row">';
    h += `<span>${escHtml(slot.label)}</span>`;
    h += `<span class="cs-row-email">${escHtml(slot.email || "unknown")}</span>`;
    h += "</div>";
  }
  h += "</div>";
  h += "</div>"; // .cs-panel-body

  if (status.toggle_error) {
    h += `<p class="am-warn">toggle failed: ${escHtml(status.toggle_error)}</p>`;
  }
  if (status.ran) {
    const sourceLabel =
      status.source === "w11" ? "W11" : status.source === "r46" ? "R46" : null;
    h += status.ok
      ? `<p class="am-dim">${sourceLabel ? `synced from ${sourceLabel} ` : ""}successfully.</p>`
      : `<p class="am-warn">sync failed: ${escHtml(status.output || "unknown error")}</p>`;
  }
  h += "</div>";
  return h;
}
