// agent-bridge-poll-render.js — pure pieces of the Poll Settings page.
//
// Everything here is a function of the /api/agent-bridge-poll payload and a
// clock reading, so it is unit-tested without a DOM: the countdown maths, the
// Windows 2000 progress bar, the settings table, the short doc, and the Mermaid
// source for the sequence diagram. js/boot/agent-bridge-poll.js does the
// polling, the ticking and the mounting.

import { renderEditForm } from "./agent-bridge-poll-form.js";
import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;

/**
 * Where the worker is in its wait, from its state file.
 * `offsetMs` is serverNow - browserNow, so a phone whose clock is off by a
 * minute still counts down correctly.
 */
export function countdown(state, nowMs, offsetMs = 0) {
  if (!state) return { mode: "unknown", secondsLeft: null, fraction: 0 };
  if (state.phase === "working")
    return { mode: "working", secondsLeft: null, fraction: 1 };
  if (state.phase !== "waiting" || !state.next_check_at)
    return { mode: "stopped", secondsLeft: null, fraction: 0 };
  const total = Math.max(1, Number(state.delay_seconds) || 1);
  const left = (Date.parse(state.next_check_at) - (nowMs + offsetMs)) / 1000;
  if (left <= 0) return { mode: "due", secondsLeft: 0, fraction: 1 };
  return {
    mode: "waiting",
    secondsLeft: left,
    fraction: Math.min(1, Math.max(0, 1 - left / total)),
  };
}

export function fmtSeconds(s) {
  if (s == null) return "—";
  const n = Math.ceil(s);
  if (n < 120) return `${n} s`;
  if (n < 7200) return `${Math.floor(n / 60)} min ${n % 60} s`;
  const h = Math.floor(n / 3600);
  return `${h} h ${Math.floor((n % 3600) / 60)} min`;
}

export function progressLabel(c) {
  if (c.mode === "working") return "Running a task now…";
  if (c.mode === "due") return "Checking now…";
  if (c.mode === "stopped") return "Not polling";
  if (c.mode === "unknown") return "No report from the worker yet";
  return `${fmtSeconds(c.secondsLeft)} until the next check`;
}

/** The bar itself; the controller only rewrites its width and label. */
export function renderProgressBar(c) {
  const pct = (c.fraction * 100).toFixed(1);
  return `<div class="w2k-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(c.fraction * 100)}">
  <div class="w2k-progress-fill" style="width:${pct}%"></div>
</div>
<p class="w2k-progress-label">${esc(progressLabel(c))}</p>`;
}

function fmtValue(row) {
  if (!row.in_file)
    return '<span class="abp-default">not set — worker default</span>';
  if (row.key === "active_hours") {
    const h = row.value;
    if (!h) return "Around the clock (nothing ignored)";
    const pad = (n) => String(n).padStart(2, "0");
    const night = h.end_hour < h.start_hour ? " (overnight)" : "";
    return `${pad(h.start_hour)}:00 to ${h.end_hour === 24 ? "midnight" : `${pad(h.end_hour)}:00`}${night} — no checks outside`;
  }
  const n = Number(row.value);
  const extra =
    row.key === "error_base_seconds" ? ", doubling each repeat" : "";
  return `${esc(row.value)} ${esc(row.unit)}${n >= 120 ? ` (${esc(fmtSeconds(n))})` : ""}${esc(extra)}`;
}

export function renderSettingsTable(d, edit = {}) {
  const rows = (d.settings || [])
    .map(
      (r) => `<tr>
    <th scope="row">${esc(r.label)}<div class="abp-key"><code>${esc(r.key)}</code></div></th>
    <td class="abp-value">${fmtValue(r)}</td>
    <td class="abp-help">${esc(r.help)}</td>
  </tr>`,
    )
    .join("");
  const warn = d.settings_error
    ? `<p class="am-warn">${esc(d.settings_error)}</p>`
    : "";
  const stale = d.settings_changed_since_start
    ? `<p class="abp-stale">The settings file changed after the worker started, so the worker is still using the old numbers. Restart it to apply them.</p>`
    : "";
  const msg = edit.message
    ? `<p class="abp-msg ${edit.ok ? "abp-ok" : "abp-err"}">${esc(edit.message)}</p>`
    : "";
  return `${msg}${warn}${stale}<table class="abp-settings">
  <thead><tr><th>Setting</th><th>Value</th><th>What it does</th></tr></thead>
  <tbody>${rows}</tbody>
</table>
<div class="abp-actions"><button type="button" class="abp-btn abp-primary" data-abp="edit">Edit settings</button></div>
<p class="srv-note">Edit changes <code>${esc(d.settings_path)}</code> and restarts the worker for you
(by hand: edit the file, then <code>${esc(d.restart_command)}</code> on DESKTOP-2OBSQMC). The worker refuses
an idle interval under 10 s so HostGator is never hammered.</p>`;
}

function statusLine(d) {
  const s = d.state || {};
  const svc = d.service || {};
  const outcome = s.outcome ? `last check: ${s.outcome}` : "no check yet";
  const when = s.checked_at
    ? ` at ${new Date(s.checked_at).toLocaleTimeString()}`
    : "";
  return `<p class="abp-status abp-${esc(d.polling)}"><strong>${esc(
    d.polling === "active"
      ? "Polling"
      : d.polling === "paused"
        ? "Paused"
        : "Not polling",
  )}</strong> — ${esc(d.reason)}.
  <span class="am-dim-inline">${esc(outcome + when)} · ${esc(String(s.checks ?? 0))} checks since start ·
  service ${esc(svc.active || "unknown")}, ${esc(svc.enabled || "unknown")} at login</span></p>`;
}

/** edit: {editing, saving, ok, message, problems} from the controller; omitted means just show. */
export function renderPollPage(d, c, edit = {}) {
  return `${statusLine(d)}
<div id="abp-progress">${renderProgressBar(c)}</div>
<h3>Settings</h3>
${edit.editing ? renderEditForm(d, edit) : renderSettingsTable(d, edit)}
<h3>Where this fits</h3>
${renderDoc(d)}
<div id="abp-diagram" aria-hidden="true"></div>`;
}

const settingValue = (d, key, fallback) => {
  const row = (d.settings || []).find((r) => r.key === key);
  return row && row.in_file && row.value != null ? row.value : fallback;
};

export function renderDoc(d) {
  return `<div class="abp-doc">
<p>ChatGPT on EG's phone cannot reach this computer: there is no open port, on purpose. Instead ChatGPT
(through the <em>StarTrekBridge</em> connector) leaves the task in a small queue on HostGator, and the
worker on this box goes and looks for it. That looking is the <strong>poll</strong>. Each check is one
HTTPS <code>GET</code> and nothing else. The full worker ADW, with the post office and the jailed Codex,
only runs once a check finds a task.</p>
<p>The timing is a trade-off. A shorter wait means ChatGPT gets its answer sooner, but it also means more
requests to the cheapest HostGator plan, which has cut EG off before for hitting it too hard. So the worker
waits ${esc(settingValue(d, "idle_seconds", 30))} s when nothing is happening, speeds up to
${esc(settingValue(d, "burst_seconds", 5))} s for a while after a task (a conversation usually has a
follow-up), backs right off for an hour if HostGator says slow down, and doubles its wait after other errors.
Showing this page never sends anything to HostGator. The countdown comes from the worker's own state file,
<code>~/.cache/agent_bridge/poll_state.json</code>.</p>
</div>`;
}

/** Mermaid sequence source, with the live numbers in the labels. No ';' — Mermaid treats it as a line break. */
export function pollSequenceDiagram(d) {
  const v = (k, f) => settingValue(d, k, f);
  const burstMin = Math.round(v("burst_window_seconds", 300) / 60);
  const slowMin = Math.round(v("slow_down_seconds", 3600) / 60);
  return `sequenceDiagram
  autonumber
  actor EG as EG (Android)
  participant GPT as ChatGPT<br/>StarTrekBridge connector
  participant GW as Gateway on HostGator<br/>PHP + SQLite queue
  participant W as Poll loop on Win11<br/>agent-bridge-worker
  participant ADW as Worker ADW<br/>claim to finalize
  participant PO as Post office
  participant CX as Codex<br/>jailed, read-only
  participant TAB as This tab
  EG->>GPT: asks for something
  GPT->>GW: submit_agent_task (OAuth)
  GW-->>GPT: task id, queued
  loop every ${v("idle_seconds", 30)} s while idle
    W->>GW: GET /worker/tasks/next
    GW-->>W: nothing queued
    W-->>TAB: poll_state.json, next check time
  end
  W->>GW: GET /worker/tasks/next
  GW-->>W: a task is waiting
  W->>ADW: run the ADW
  ADW->>GW: claim with a lease
  ADW->>PO: hand the task off
  PO->>CX: codex exec, read-only sandbox
  CX-->>PO: answer
  PO-->>ADW: reply
  ADW->>GW: heartbeat, events, complete
  Note over W: ${v("burst_seconds", 5)} s checks for ${burstMin} min after a task
  GPT->>GW: get_agent_task_result
  GW-->>GPT: the result
  GPT-->>EG: reads it out
  alt HostGator answers 429 or 503
    Note over W,GW: wait ${slowMin} min before the next check
  else any other error
    Note over W,GW: wait ${v("error_base_seconds", 30)} s, doubling up to ${v("error_max_seconds", 900)} s
  end`;
}
