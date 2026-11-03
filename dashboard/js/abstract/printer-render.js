// printer-render.js — pure pieces of the Printer tab under System Status.
//
// Everything here is a function of the /api/printer payload, so it is tested
// without a DOM. js/boot/printer-panel.js fetches, mounts and handles clicks.
// The wording keeps "left the Windows queue" apart from "printed on paper":
// no printer here confirms paper, so the page never says it did.

import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;

const STATE_TEXT = {
  accepted: "Accepted",
  queued: "Queued",
  submitting: "Sending to Windows",
  submitted_to_spooler: "In the Windows queue",
  completed_per_spooler: "Left the Windows queue",
  canceled: "Canceled",
  failed: "Failed",
  ambiguous: "Unknown — may have printed",
};

const OPEN_STATES = new Set(["accepted", "queued", "submitted_to_spooler"]);

export function stateText(state) {
  return STATE_TEXT[state] || String(state || "unknown");
}

/** A job can be canceled from here only while it has not left the queue. */
export function canCancel(job) {
  return OPEN_STATES.has(job?.state);
}

export function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}

/** Tab colour: green when printing is switched on and a default printer answered. */
export function tabClassFor(payload) {
  return payload?.ok && payload.enabled && payload.default
    ? "server-up"
    : "poll-disabled";
}

export function renderPrinters(payload) {
  if (!payload.printers.length)
    return '<p class="am-dim">Windows reported no printers.</p>';
  const rows = payload.printers
    .map(
      (
        p,
      ) => `<tr><td>${esc(p.name)}${p.printer_id === payload.default ? ' <span class="prn-default">default</span>' : ""}</td>
<td><code>${esc(p.printer_id)}</code></td><td>${esc(p.status)}</td></tr>`,
    )
    .join("\n");
  return `<table class="prn-table"><thead><tr><th>Printer</th><th>Id</th><th>Status</th></tr></thead>
<tbody>${rows}</tbody></table>`;
}

export function renderJobs(jobs) {
  if (!jobs.length) return '<p class="am-dim">No print jobs yet.</p>';
  const rows = jobs
    .map(
      (
        j,
      ) => `<tr class="prn-${esc(j.state)}"><td>${esc(j.title || "(untitled)")}</td><td>${esc(fmtTime(j.submitted_at))}</td>
<td>${esc(j.printer || "—")}</td><td title="${esc(j.detail)}">${esc(stateText(j.state))}</td>
<td>${canCancel(j) ? `<button type="button" class="prn-cancel" data-prn="cancel" data-job="${esc(j.job_id)}">Cancel</button>` : ""}</td></tr>`,
    )
    .join("\n");
  return `<table class="prn-table"><thead><tr><th>Document</th><th>Sent</th><th>Printer</th><th>Status</th><th></th></tr></thead>
<tbody>${rows}</tbody></table>`;
}

export function renderPrinterPage(payload, ui = {}) {
  if (!payload) return '<p class="am-dim">Checking&hellip;</p>';
  const note = ui.message
    ? `<p class="${ui.ok ? "prn-ok" : "am-warn"}">${esc(ui.message)}</p>`
    : "";
  if (!payload.ok) {
    return `${note}<p class="am-warn">Could not ask Windows about printers: ${esc(payload.error)}</p>
<button type="button" data-prn="refresh">Try again</button>`;
  }
  const switchLine = payload.enabled
    ? '<p class="srv-note">Printing is <strong>on</strong>. ChatGPT can print only after you ask it to, through StarTrekBridge.</p>'
    : '<p class="srv-note">Printing is <strong>off</strong> on this computer (no <code>~/.config/startrek_printer/enabled</code>). Nothing can print until it is switched on.</p>';
  const test = payload.enabled
    ? `<button type="button" data-prn="test" ${ui.busy ? "disabled" : ""}>Print the test page</button>`
    : "";
  return `${note}${switchLine}
<h3>Printers</h3>${renderPrinters(payload)}
<p class="am-dim">${payload.documents} document(s) waiting in the print outbox.</p>
<h3>Recent jobs</h3>${renderJobs(payload.recent)}
<p class="am-dim">"Left the Windows queue" means Windows finished with the job; no printer here confirms that paper came out.</p>
<p>${test} <button type="button" data-prn="refresh">Refresh</button></p>`;
}
