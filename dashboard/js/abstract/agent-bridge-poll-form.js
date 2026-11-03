// agent-bridge-poll-form.js — the Poll Settings edit form, as pure functions.
//
// renderEditForm() draws the inputs from the /api/agent-bridge-poll payload;
// readForm() turns what was typed back into the JSON the save route takes.
// The limits (idle never under 10 s, and so on) are the worker's, checked by
// adws/adw_bridge_poll_settings.py; this only catches what is not a number,
// so the answer shown is always the worker's own.

import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;

export const NUMBER_KEYS = [
  "idle_seconds",
  "burst_seconds",
  "burst_window_seconds",
  "slow_down_seconds",
  "error_base_seconds",
  "error_max_seconds",
];

const DEFAULTS = {
  idle_seconds: 30,
  burst_seconds: 5,
  burst_window_seconds: 300,
  slow_down_seconds: 3600,
  error_base_seconds: 30,
  error_max_seconds: 900,
};

const pad = (n) => String(n).padStart(2, "0");
const hourName = (h) => (h === 24 ? "midnight" : `${pad(h)}:00`);

function hourOptions(from, to, selected) {
  let out = "";
  for (let h = from; h <= to; h++)
    out += `<option value="${h}"${h === selected ? " selected" : ""}>${hourName(h)}</option>`;
  return out;
}

/** problems: [{field, message}] from the last save, shown beside their field. */
function problemFor(problems, key) {
  const mine = (problems || []).filter((p) => p.field === key);
  return mine.length
    ? `<div class="abp-problem">${mine.map((p) => esc(p.message)).join("<br>")}</div>`
    : "";
}

function numberInput(row, problems) {
  const value =
    row.in_file && row.value != null ? row.value : DEFAULTS[row.key];
  return `<input class="abp-input" type="number" name="${esc(row.key)}" value="${esc(value)}"
    min="0" step="any" inputmode="decimal" aria-label="${esc(row.label)}"> s${problemFor(problems, row.key)}`;
}

function hoursInput(row, problems) {
  const h = row.in_file ? row.value : null;
  const start = h ? h.start_hour : 7;
  const end = h ? h.end_hour : 24;
  const off = h ? "" : " disabled";
  return `<label class="abp-check"><input type="checkbox" name="around_clock"${h ? "" : " checked"}>
    Around the clock (nothing ignored)</label>
  <div class="abp-hours">From <select name="start_hour"${off} aria-label="Start hour">${hourOptions(0, 23, start)}</select>
    to <select name="end_hour"${off} aria-label="End hour">${hourOptions(1, 24, end)}</select></div>
  ${problemFor(problems, "active_hours")}`;
}

export function renderEditForm(d, edit = {}) {
  const rows = (d.settings || [])
    .map(
      (r) => `<tr>
    <th scope="row">${esc(r.label)}<div class="abp-key"><code>${esc(r.key)}</code></div></th>
    <td class="abp-value">${r.key === "active_hours" ? hoursInput(r, edit.problems) : numberInput(r, edit.problems)}</td>
    <td class="abp-help">${esc(r.help)}</td>
  </tr>`,
    )
    .join("");
  const general = problemFor(edit.problems, "");
  const msg = edit.message
    ? `<p class="abp-msg ${edit.ok ? "abp-ok" : "abp-err"}">${esc(edit.message)}</p>`
    : "";
  const busy = edit.saving ? " disabled" : "";
  return `${msg}${general}<form class="abp-form" data-abp="form" novalidate>
<table class="abp-settings">
  <thead><tr><th>Setting</th><th>Value</th><th>What it does</th></tr></thead>
  <tbody>${rows}</tbody>
</table>
<div class="abp-actions">
  <button type="submit" class="abp-btn abp-primary" data-abp="save"${busy}>${edit.saving ? "Saving and restarting…" : "Save and restart worker"}</button>
  <button type="button" class="abp-btn" data-abp="cancel"${busy}>Cancel</button>
</div>
<p class="srv-note">Saving backs up <code>poll_settings.json</code> to <code>poll_settings.json.bak</code>, then
restarts the worker so it reads the new numbers. It will not restart in the middle of a ChatGPT task.</p>
</form>`;
}

/**
 * values: {idle_seconds: "45", ..., around_clock: true|false, start_hour: "7", end_hour: "24"}.
 * Returns {payload} or {problems} when something is not a number.
 */
export function readForm(values) {
  const payload = {};
  const problems = [];
  for (const key of NUMBER_KEYS) {
    const text = String(values[key] ?? "").trim();
    const n = Number(text);
    if (text === "" || !Number.isFinite(n))
      problems.push({ field: key, message: "Enter a number of seconds." });
    else payload[key] = n;
  }
  payload.active_hours = values.around_clock
    ? null
    : {
        start_hour: Number(values.start_hour),
        end_hour: Number(values.end_hour),
      };
  return problems.length ? { problems } : { payload };
}

/** Reads a live <form> into the shape readForm() takes. */
export function formValues(form) {
  const v = {};
  for (const key of [...NUMBER_KEYS, "start_hour", "end_hour"])
    v[key] = form.elements[key]?.value;
  v.around_clock = !!form.elements.around_clock?.checked;
  return v;
}

/** The payload with what was typed in place of the saved values, so a refused form keeps the typing. */
export function withTyped(d, values) {
  const typed = (r) => {
    if (r.key !== "active_hours")
      return { ...r, value: values[r.key], in_file: true };
    if (values.around_clock) return { ...r, value: null, in_file: true };
    return {
      ...r,
      value: {
        start_hour: Number(values.start_hour),
        end_hour: Number(values.end_hour),
      },
      in_file: true,
    };
  };
  return { ...d, settings: (d.settings || []).map(typed) };
}
