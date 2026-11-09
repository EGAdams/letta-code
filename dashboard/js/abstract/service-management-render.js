// Pure presentation of service observations. A running worker does not prove
// that it consumes tasks; that evidence stays on Worker Activity.
import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;
export const serviceStatusClass = (status) =>
  status === "up" ? "server-up" : status === "down" ? "server-down" : "server-concern";
const date = (value) => value ? new Date(value * 1000).toLocaleString() : "Unavailable";
const duration = (seconds) => {
  if (seconds == null) return "Unavailable";
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.floor(seconds % 60)}s`;
};

export function renderServiceDetail(service, payload) {
  const warnings = [payload.configuration_error, payload.history_error, payload.fetch_error]
    .filter(Boolean).map((error) => `<p class="am-warn">${esc(error)}</p>`).join("");
  if (!service) return `${warnings}<p class="am-dim">Waiting for service observations…</p>`;
  const fields = [
    ["Status", service.status === "up" ? "Running" : service.status === "down" ? "DOWN" : service.status === "concern" ? "Needs attention" : "Unknown"],
    ["Unit", service.unit], ["Scope", service.scope],
    ["State", `${service.active} / ${service.sub || "—"}`],
    ["Installed", service.loaded || "Unknown"], ["Enabled at startup", service.enabled],
    ["Process ID", service.pid || "—"], ["Automatic restarts", service.restarts],
    ["Last result", service.result || "—"], ["State since", date(service.since)],
    ["Down since", date(service.down_since)],
    ["Current downtime", service.status === "up" ? "0m 0s" : duration(service.down_for_seconds)],
    ["Last checked", date(payload.checked_at)],
  ];
  const history = (service.events || []).map((event) =>
    `<tr><td>${esc(date(event.at))}</td><td>${esc(event.status)}</td><td>${esc(event.detail)}${event.outage_seconds != null ? ` · Recovered after ${esc(duration(event.outage_seconds))}` : ""}</td></tr>`
  ).join("");
  return `${warnings}<h3>${esc(service.label)}</h3><p>${esc(service.detail)}</p>
    <dl class="service-management-facts">${fields.map(([name, value]) => `<dt>${esc(name)}</dt><dd>${esc(value ?? "—")}</dd>`).join("")}</dl>
    <h3>Observed service history</h3><p class="am-dim">The dashboard server checks every 15 seconds, even with the browser closed. Outages between checks or while the dashboard server is stopped may be missed. History survives dashboard restarts.</p>
    <div class="worker-activity-table-wrap"><table class="worker-activity-table"><thead><tr><th>Observed at</th><th>Status</th><th>Details</th></tr></thead><tbody>${history || '<tr><td colspan="3">No transitions recorded.</td></tr>'}</tbody></table></div>`;
}
