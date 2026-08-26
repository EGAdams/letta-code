import { PollingController } from "../abstract/polling-controller.interface.js";

/**
 * buildOauthAccountSelect — the OAuth-account twin of buildModelRow
 * (detail-renderers.js): a bare <select> backed by /api/agent-oauth-account,
 * fetching {current, options:[{provider,account,label}]} and PATCHing on
 * change. Lists every provider row across BOTH model families (not just the
 * agent's current one) so any of the four human/family token combinations is
 * always reachable from any agent's Token dropdown -- picking one outside
 * the agent's current family also jumps that agent's model family (the
 * server picks a default model for the target family; see
 * patch_agent_oauth_account). `onSwitched(result)` lets the caller resync
 * its paired Model dropdown from `result.model` since this select alone
 * doesn't own that field.
 */
export function buildOauthAccountSelect({
  el,
  http,
  agentId,
  showStatus,
  getPendingModel = () => "",
  onSwitched = () => {},
}) {
  const select = el("select", { disabled: true });

  let current = "";
  const load = () => {
    const pending = getPendingModel();
    const url =
      `/api/agent-oauth-account?agent=${encodeURIComponent(agentId)}` +
      (pending ? `&model=${encodeURIComponent(pending)}` : "");
    return http
      .getJSON(url)
      .then((d) => {
        if (!d || !d.ok || !Array.isArray(d.options) || !d.options.length) {
          select.disabled = true;
          return;
        }
        select.innerHTML = "";
        for (const opt of d.options) {
          select.appendChild(
            el("option", { value: opt.provider, textContent: opt.label }),
          );
        }
        // A reload triggered by the model dropdown changing races the model
        // PATCH itself -- the server's live llm_config may still show the
        // OLD provider for a moment, so its "current" can come back blank or
        // stale. Once we already have a selection, keep it rather than
        // trusting a server read that's mid-transition; only a fresh mount
        // (current === "") defers to the server's actual current.
        const optionKeys = d.options.map((opt) => opt.provider);
        current =
          (current && optionKeys.includes(current) && current) ||
          d.current ||
          d.options[0].provider;
        select.value = current;
        select.disabled = false;
      })
      .catch(() => {
        select.disabled = true;
      });
  };

  select.addEventListener("change", async () => {
    const next = select.value;
    select.disabled = true;
    showStatus(`Switching token…`);
    try {
      const r = await http.postJSON("/api/agent-oauth-account", {
        agent: agentId,
        provider: next,
      });
      if (r?.ok) {
        current = r.provider || next;
        showStatus(`Token switched.`);
        onSwitched(r);
        // Optional chaining: see the matching note in buildModelRow
        // (detail-renderers.js) -- a throw here must never look like the
        // account switch itself failing.
        select.dispatchEvent?.(
          new CustomEvent("agent-oauth-account:changed", {
            bubbles: true,
            detail: { agentId, account: r.account, provider: current },
          }),
        );
      } else {
        select.value = current;
        showStatus(r?.error || "Token change failed.", true);
      }
    } catch (e) {
      select.value = current;
      showStatus(`Token change failed: ${e.message}`, true);
    } finally {
      select.disabled = false;
    }
  });

  load();
  return { select, reload: load };
}

/**
 * buildClaudeSdkAccountSelect — the read-only executor's account selector.
 * Unlike a Letta-agent account switch, this syncs a credential into the
 * shared Frita executor and therefore has no agent ID.
 */
export function buildClaudeSdkAccountSelect({ el, http, showStatus }) {
  const select = el("select", { disabled: true });
  let current = "";

  const load = () =>
    http
      .getJSON("/api/claude-sdk-account")
      .then((d) => {
        if (!d || !d.ok || !Array.isArray(d.options) || !d.options.length) {
          select.disabled = true;
          return;
        }
        select.innerHTML = "";
        for (const opt of d.options) {
          select.appendChild(
            el("option", { value: opt.account, textContent: opt.label }),
          );
        }
        const optionKeys = d.options.map((opt) => opt.account);
        current =
          (current && optionKeys.includes(current) && current) ||
          d.current ||
          d.options[0].account;
        select.value = current;
        select.disabled = false;
      })
      .catch(() => {
        select.disabled = true;
      });

  select.addEventListener("change", async () => {
    const next = select.value;
    select.disabled = true;
    showStatus(`Syncing Claude SDK token to ${next}…`);
    try {
      const result = await http.postJSON("/api/claude-sdk-account", {
        account: next,
      });
      if (!result?.ok) {
        select.value = current;
        showStatus(result?.error || "Claude SDK token change failed.", true);
        return;
      }
      current = result.current || next;
      showStatus(`Claude SDK token set to ${current}.`);
      select.dispatchEvent?.(
        new CustomEvent("claude-sdk-account:changed", {
          bubbles: true,
          detail: { agentId: "tool-run-claude-code-sdk" },
        }),
      );
      await load();
    } catch (e) {
      select.value = current;
      showStatus(`Claude SDK token change failed: ${e.message}`, true);
    } finally {
      select.disabled = false;
    }
  });

  load();
  return { select, reload: load };
}

function barClassFor(pct) {
  if (pct == null) return "";
  if (pct <= 10) return "is-critical";
  if (pct <= 30) return "is-low";
  return "";
}

/**
 * AgentAssignmentsController — concrete PollingController for the Model
 * Stats "Agent Assignments" tab: one row per Letta agent with a live model
 * dropdown, a live OAuth-account dropdown, and a weekly-remaining bar fed by
 * one bulk /api/model-stats-agents poll (the two dropdowns build/fetch their
 * own options once per agent; only the bar updates every tick).
 */
export class AgentAssignmentsController extends PollingController {
  constructor({
    http,
    el,
    buildModelSelect,
    container,
    onStatus = () => {},
    ...opts
  } = {}) {
    super({ intervalMs: 20000, ...opts });
    if (!http || !el || !buildModelSelect || !container) {
      throw new Error(
        "AgentAssignmentsController requires { http, el, buildModelSelect, container }",
      );
    }
    this._http = http;
    this._el = el;
    this._buildModelSelect = buildModelSelect;
    this._container = container;
    this._onStatus = onStatus;
    this._rowsById = new Map();
  }

  /** @override */
  async poll() {
    let rows;
    try {
      rows = await this._http.getJSON("/api/model-stats-agents");
    } catch (e) {
      this._onStatus(`Failed to load agent assignments: ${e.message}`, true);
      return;
    }
    if (!this._table) this._renderShell();
    for (const row of rows) this._renderRow(row);
  }

  _renderShell() {
    const el = this._el;
    const status = el("p", { className: "win98-dim" });
    this._status = status;
    const table = el("table");
    const thead = el("thead");
    const headRow = el("tr");
    for (const label of [
      "Agent / Tool",
      "Model",
      "Token",
      "Weekly Remaining",
    ]) {
      headRow.appendChild(el("th", { textContent: label }));
    }
    thead.appendChild(headRow);
    const tbody = el("tbody");
    table.append(thead, tbody);
    this._container.innerHTML = "";
    this._container.append(status, table);
    this._table = table;
    this._tbody = tbody;

    // Selects bubble a "…:changed" CustomEvent on a successful sync/PATCH
    // (see buildModelRow, buildOauthAccountSelect, and
    // buildClaudeSdkAccountSelect). One delegated listener
    // catches either and refreshes that row's bar immediately instead of
    // waiting up to intervalMs for the next poll.
    for (const type of [
      "agent-model:changed",
      "agent-oauth-account:changed",
      "claude-sdk-account:changed",
    ]) {
      tbody.addEventListener(type, (evt) => {
        this._refreshRowBar(evt.detail.agentId);
      });
    }
  }

  /** Re-fetch just this row's bar after a model/account switch, bypassing
   * the bulk cache -- a switch just PATCHed the live provider, so a cached
   * pre-switch value would show the old account's percentage. Blinks the
   * bar for the duration of the fetch so a percentage that visibly doesn't
   * move yet still signals "recalculating", not "nothing happened". */
  async _refreshRowBar(agentId) {
    const entry = this._rowsById.get(agentId);
    entry?.fill?.classList.add("is-recalculating");
    try {
      const rows = await this._http.getJSON(
        "/api/model-stats-agents?refresh=1",
      );
      const row = rows.find((r) => r.id === agentId);
      if (row) this._renderRow(row);
    } catch {
      // leave the last-known value in place; next scheduled poll will retry
    } finally {
      entry?.fill?.classList.remove("is-recalculating");
    }
  }

  /** Show a transient status line above the table (model/token switch results). */
  _showStatus(msg, isError = false) {
    if (!this._status) return;
    this._status.textContent = msg;
    this._status.classList.toggle("win98-dim", !isError);
  }

  _renderRow(row) {
    if (row.assignment_kind === "tool") {
      this._renderToolRow(row);
      return;
    }
    if (row.assignment_kind === "account") {
      this._renderAccountRow(row);
      return;
    }

    let entry = this._rowsById.get(row.id);
    if (!entry) {
      const el = this._el;
      const tr = el("tr");
      tr.appendChild(el("td", { textContent: row.name }));

      const modelTd = el("td");
      const modelSelect = this._buildModelSelect({
        el,
        http: this._http,
        agentId: row.id,
        showStatus: (msg, isError) => this._showStatus(msg, isError),
      });
      modelTd.appendChild(modelSelect);
      tr.appendChild(modelTd);

      const accountTd = el("td");
      const { select: accountSelect, reload: reloadAccountOptions } =
        buildOauthAccountSelect({
          el,
          http: this._http,
          agentId: row.id,
          showStatus: (msg, isError) => this._showStatus(msg, isError),
          getPendingModel: () => modelSelect.value,
          // A Token switch across families has no in-family model id to
          // keep, so the server picks a default and reports it back here --
          // resync the Model dropdown's displayed value immediately rather
          // than waiting for its own next /api/agent-model poll.
          onSwitched: (result) => {
            if (result?.model) modelSelect.value = result.model;
          },
        });
      // The account list depends on the model's family (claude vs chatgpt).
      // Refresh it the instant the model dropdown changes -- using the
      // not-yet-saved pending value via getPendingModel above -- so the
      // labels shown are never a stale family's (see win98 agent-assignments
      // "100% remaining"/wrong-account-label bug fixed 2026-08-22).
      modelSelect.addEventListener("change", () => reloadAccountOptions());
      accountTd.appendChild(accountSelect);
      tr.appendChild(accountTd);

      const barTd = el("td", { className: "win98-bar-cell" });
      const track = el("div", { className: "win98-bar-track" });
      const fill = el("div", { className: "win98-bar-fill" });
      const label = el("div", { className: "win98-bar-label" });
      track.append(fill, label);
      barTd.appendChild(track);
      tr.appendChild(barTd);

      this._tbody.appendChild(tr);
      entry = { tr, fill, label };
      this._rowsById.set(row.id, entry);
    }

    const pct = row.weekly_percent_remaining;
    entry.fill.className = `win98-bar-fill ${barClassFor(pct)}`.trim();
    entry.fill.style.width =
      pct == null ? "0%" : `${Math.max(0, Math.min(100, pct))}%`;
    entry.label.textContent = pct == null ? "?" : `${pct}%`;
  }

  _renderToolRow(row) {
    let entry = this._rowsById.get(row.id);
    if (!entry) {
      const el = this._el;
      const tr = el("tr", { className: "win98-tool-assignment" });
      tr.appendChild(el("td", { textContent: row.name }));
      tr.appendChild(el("td", { textContent: row.model || "—" }));
      const tokenTd = el("td");
      const { select: accountSelect } = buildClaudeSdkAccountSelect({
        el,
        http: this._http,
        showStatus: (msg, isError) => this._showStatus(msg, isError),
      });
      const token = el("div", { className: "win98-assignment-token" });
      tokenTd.append(accountSelect, token);
      tr.appendChild(tokenTd);
      tr.appendChild(
        el("td", {
          className: "win98-assignment-unavailable",
          textContent: "—",
        }),
      );
      this._tbody.appendChild(tr);
      entry = { tr, select: accountSelect, token };
      this._rowsById.set(row.id, entry);
    }

    entry.token.textContent =
      row.token_status === "up"
        ? ""
        : row.token_status_detail || "Token status unavailable";
    entry.token.className = `win98-assignment-token is-${row.token_status || "unknown"}`;
    if (row.account) entry.select.value = row.account;
  }

  /** Read-only row for an OAuth account that backs no current agent (e.g. a
   * held-in-reserve failover token) -- no model/account dropdowns, just the
   * label and its weekly-remaining bar so an unused token's expiry is still
   * visible on the tab. */
  _renderAccountRow(row) {
    let entry = this._rowsById.get(row.id);
    if (!entry) {
      const el = this._el;
      const tr = el("tr", { className: "win98-unassigned-account" });
      tr.appendChild(el("td", { textContent: row.name }));
      tr.appendChild(el("td", { textContent: row.model || "—" }));
      tr.appendChild(el("td", { textContent: row.account_label }));

      const barTd = el("td", { className: "win98-bar-cell" });
      const track = el("div", { className: "win98-bar-track" });
      const fill = el("div", { className: "win98-bar-fill" });
      const label = el("div", { className: "win98-bar-label" });
      track.append(fill, label);
      barTd.appendChild(track);
      tr.appendChild(barTd);

      this._tbody.appendChild(tr);
      entry = { tr, fill, label };
      this._rowsById.set(row.id, entry);
    }

    const pct = row.weekly_percent_remaining;
    entry.fill.className = `win98-bar-fill ${barClassFor(pct)}`.trim();
    entry.fill.style.width =
      pct == null ? "0%" : `${Math.max(0, Math.min(100, pct))}%`;
    entry.label.textContent = pct == null ? "?" : `${pct}%`;
  }
}
