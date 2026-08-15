/**
 * ChatGPT provider account status — shape guard + pure rendering, no
 * DOM/fetch. Mirrors codex-sync-status.js's split: the server's Pydantic
 * StrictModel (chatgpt_provider_status.ChatGptProviderAccountStatus) guards
 * this shape on the way out; assertChatGptProviderAccountStatus is the
 * mirror guard on the way in, since a plain fetch response carries no
 * compile-time type in vanilla JS.
 */

import { escHtml } from "./codex-sync-status.js";

/**
 * @param {any} opt
 * @returns {{key:string, label:string}}
 */
export function assertChatGptProviderAccountOption(opt) {
  if (!opt || typeof opt !== "object") {
    throw new TypeError(
      `ChatGptProviderAccountOption: expected object, got ${typeof opt}`,
    );
  }
  if (typeof opt.key !== "string") {
    throw new TypeError(
      `ChatGptProviderAccountOption.key: expected string, got ${typeof opt.key}`,
    );
  }
  if (typeof opt.label !== "string") {
    throw new TypeError(
      `ChatGptProviderAccountOption.label: expected string, got ${typeof opt.label}`,
    );
  }
  return { key: opt.key, label: opt.label };
}

/**
 * Validate the /api/chatgpt-provider-account-status|-account payload shape.
 * @param {any} status
 * @returns {{active_email:string|null, sources:Array<{key:string,label:string}>,
 *            ran:boolean, ok:boolean|null, text:string|null, source:string|null}}
 */
export function assertChatGptProviderAccountStatus(status) {
  if (!status || typeof status !== "object") {
    throw new TypeError(
      `ChatGptProviderAccountStatus: expected object, got ${typeof status}`,
    );
  }
  if (status.active_email != null && typeof status.active_email !== "string") {
    throw new TypeError(
      `ChatGptProviderAccountStatus.active_email: expected string|null, got ${typeof status.active_email}`,
    );
  }
  if (!Array.isArray(status.sources)) {
    throw new TypeError(
      `ChatGptProviderAccountStatus.sources: expected array, got ${typeof status.sources}`,
    );
  }
  return {
    active_email: status.active_email ?? null,
    sources: status.sources.map(assertChatGptProviderAccountOption),
    ran: Boolean(status.ran),
    ok: status.ok ?? null,
    text: status.text ?? null,
    source: status.source ?? null,
  };
}

/**
 * Pure render: validated status → panel HTML.
 * @param {any} rawStatus
 * @returns {string}
 */
export function renderChatGptProviderAccountPanel(rawStatus) {
  if (!rawStatus) {
    return '<div class="cs-panel"><p class="am-dim">live provider token: no data</p></div>';
  }
  let status;
  try {
    status = assertChatGptProviderAccountStatus(rawStatus);
  } catch (e) {
    return `<div class="cs-panel"><p class="am-warn">live provider token: bad status payload — ${escHtml(e.message)}</p></div>`;
  }

  let h = '<div class="cs-panel">';
  h +=
    '<div class="cs-panel-toolbar"><h4>Live provider token (Mazda + fleet LLM)</h4></div>';
  h += '<div class="cs-panel-body">';
  h += '<div class="cs-panel-head">';
  h += `<span>Currently: <strong>${escHtml(status.active_email || "unknown")}</strong></span>`;
  h += "</div>";
  h += '<div class="cs-panel-actions">';
  for (const opt of status.sources) {
    h += `<button type="button" class="cs-swap-btn" id="cgpa-set-${escHtml(opt.key)}-btn" title="Install ${escHtml(opt.label)}'s token as the live provider row">Set to ${escHtml(opt.label)}</button>`;
  }
  h += "</div>";
  h += "</div>"; // .cs-panel-body

  if (status.ran) {
    const opt = status.sources.find((s) => s.key === status.source);
    const label = opt ? opt.label : status.source;
    h += status.ok
      ? `<p class="am-dim">live provider token set to ${escHtml(label)}.</p>`
      : `<p class="am-warn">swap failed: ${escHtml(status.text || "unknown error")}</p>`;
  }
  h += "</div>";
  return h;
}
