import { PollingController } from "../abstract/polling-controller.interface.js";

/**
 * AgentActivityPoller — concrete PollingController for the agent sidebar
 * activity colours. Every 5s it GETs `/api/agent-activity` (a map of
 * agentId → status) and reports each entry through the injected `setStatus`
 * callback (the boot's setAgentTabStatus). Fetch errors are swallowed so a
 * transient blip never tears down the loop.
 *
 * Reproduces the inline startActivityPoll() IIFE, but the transport and the
 * status sink are injected ports so the loop is unit-testable.
 */
export class AgentActivityPoller extends PollingController {
  constructor({ http, setStatus, url = "/api/agent-activity", ...opts } = {}) {
    super({ intervalMs: 5000, ...opts });
    if (!http || !setStatus) {
      throw new Error("AgentActivityPoller requires { http, setStatus }");
    }
    this._http = http;
    this._setStatus = setStatus;
    this._url = url;
  }

  /** @override */
  async poll() {
    let activity;
    try {
      activity = await this._http.getJSON(this._url);
    } catch {
      return; // transient failure — keep polling
    }
    for (const [id, status] of Object.entries(activity || {})) {
      this._setStatus(id, status);
    }
  }
}
