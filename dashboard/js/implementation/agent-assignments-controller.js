import { PollingController } from "../abstract/polling-controller.interface.js";
import {
  buildClaudeSdkAccountSelect,
  buildOauthAccountSelect,
} from "./assignment-account-selects.js";
import {
  buildAssignmentUsageBar,
  renderAssignmentUsageBar,
} from "./assignment-usage-bar.js";
import { buildModelRow } from "./detail-renderers.js";

export class AgentAssignmentsController extends PollingController {
  constructor({ http, el, container, onStatus = () => {}, ...opts } = {}) {
    super({ intervalMs: 20000, ...opts });
    if (!http || !el || !container) {
      throw new Error(
        "AgentAssignmentsController requires { http, el, container }",
      );
    }
    this._http = http;
    this._el = el;
    this._container = container;
    this._onStatus = onStatus;
    this._rowsById = new Map();
  }

  async poll() {
    let rows;
    try {
      rows = await this._http.getJSON("/api/model-stats-agents");
    } catch (error) {
      this._onStatus(
        `Failed to load agent assignments: ${error.message}`,
        true,
      );
      return;
    }
    if (!this._table) this._renderShell();
    for (const row of rows) this._renderRow(row);
  }

  _renderShell() {
    const status = this._el("p", { className: "win98-dim" });
    const table = this._el("table");
    const thead = this._el("thead");
    const headRow = this._el("tr");
    for (const label of [
      "Agent / Tool",
      "Model",
      "Token",
      "Weekly Remaining",
    ]) {
      headRow.appendChild(this._el("th", { textContent: label }));
    }
    thead.appendChild(headRow);
    const tbody = this._el("tbody");
    table.append(thead, tbody);
    this._container.innerHTML = "";
    this._container.append(status, table);
    this._status = status;
    this._table = table;
    this._tbody = tbody;
    for (const type of [
      "agent-model:changed",
      "agent-oauth-account:changed",
      "claude-sdk-account:changed",
    ]) {
      tbody.addEventListener(type, (event) => {
        this._refreshRowBar(event.detail.agentId);
      });
    }
  }

  async _refreshRowBar(agentId) {
    const entry = this._rowsById.get(agentId);
    entry?.fill?.classList.add("is-recalculating");
    try {
      const rows = await this._http.getJSON(
        "/api/model-stats-agents?refresh=1",
      );
      const row = rows.find((candidate) => candidate.id === agentId);
      if (row) this._renderRow(row);
    } catch {
      // Keep the last good reading; the scheduled poll will retry.
    } finally {
      entry?.fill?.classList.remove("is-recalculating");
    }
  }

  _showStatus(message, isError = false) {
    if (!this._status) return;
    this._status.textContent = message;
    this._status.classList.toggle("win98-dim", !isError);
  }

  _renderRow(row) {
    if (row.assignment_kind === "tool") return this._renderToolRow(row);
    if (row.assignment_kind === "account") return this._renderAccountRow(row);
    return this._renderAgentRow(row);
  }

  _renderAgentRow(row) {
    let entry = this._rowsById.get(row.id);
    if (!entry) {
      const el = this._el;
      const tr = el("tr");
      tr.appendChild(el("td", { textContent: row.name }));
      let modelSelect;
      let reloadModelOptions;
      const { select: accountSelect } = buildOauthAccountSelect({
        el,
        http: this._http,
        agentId: row.id,
        showStatus: (message, error) => this._showStatus(message, error),
        getPendingModel: () => modelSelect?.value || "",
        onSwitched: () => reloadModelOptions?.(),
      });
      const modelCell = el("td");
      ({ select: modelSelect, reload: reloadModelOptions } = buildModelRow({
        el,
        http: this._http,
        agentId: row.id,
        showStatus: (message, error) => this._showStatus(message, error),
        getPendingProvider: () => accountSelect.value,
      }));
      modelCell.appendChild(modelSelect);
      const accountCell = el("td");
      accountCell.appendChild(accountSelect);
      const usage = buildAssignmentUsageBar(el);
      tr.append(modelCell, accountCell, usage.cell);
      this._tbody.appendChild(tr);
      entry = { tr, fill: usage.fill, label: usage.label };
      this._rowsById.set(row.id, entry);
    }
    renderAssignmentUsageBar(entry, row, { tokenAware: true });
  }

  _renderToolRow(row) {
    let entry = this._rowsById.get(row.id);
    if (!entry) {
      const el = this._el;
      const tr = el("tr", { className: "win98-tool-assignment" });
      tr.appendChild(el("td", { textContent: row.name }));
      tr.appendChild(el("td", { textContent: row.model || "—" }));
      const tokenCell = el("td");
      const { select } = buildClaudeSdkAccountSelect({
        el,
        http: this._http,
        showStatus: (message, error) => this._showStatus(message, error),
      });
      const token = el("div", { className: "win98-assignment-token" });
      tokenCell.append(select, token);
      const usage = buildAssignmentUsageBar(el);
      tr.append(tokenCell, usage.cell);
      this._tbody.appendChild(tr);
      entry = { tr, select, token, fill: usage.fill, label: usage.label };
      this._rowsById.set(row.id, entry);
    }
    entry.token.textContent =
      row.token_status === "up"
        ? ""
        : row.token_status_detail || "Token status unavailable";
    entry.token.className = `win98-assignment-token is-${row.token_status || "unknown"}`;
    if (row.account) entry.select.value = row.account;
    renderAssignmentUsageBar(entry, row, { tokenAware: true });
  }

  _renderAccountRow(row) {
    let entry = this._rowsById.get(row.id);
    if (!entry) {
      const el = this._el;
      const tr = el("tr", { className: "win98-unassigned-account" });
      tr.appendChild(el("td", { textContent: row.name }));
      tr.appendChild(el("td", { textContent: row.model || "—" }));
      tr.appendChild(el("td", { textContent: row.account_label }));
      const usage = buildAssignmentUsageBar(el);
      tr.appendChild(usage.cell);
      this._tbody.appendChild(tr);
      entry = { tr, fill: usage.fill, label: usage.label };
      this._rowsById.set(row.id, entry);
    }
    renderAssignmentUsageBar(entry, row);
  }
}
