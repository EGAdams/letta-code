import { PollingController } from "../abstract/polling-controller.interface.js";

/**
 * AgentHealthPoller — polls /api/agent-health every 30s and forwards each
 * agent's {ok, text} to the injected setHealth(agentId, ok, text) callback.
 *
 * Health is structural (required tools present, ID resolvable) not activity-
 * based, so it polls less frequently than AgentActivityPoller and uses a
 * separate CSS class so the two don't stomp each other.
 */
export class AgentHealthPoller extends PollingController {
  constructor({ http, setHealth, url = "/api/agent-health", ...opts } = {}) {
    super({ intervalMs: 30000, ...opts });
    if (!http || !setHealth) {
      throw new Error("AgentHealthPoller requires { http, setHealth }");
    }
    this._http = http;
    this._setHealth = setHealth;
    this._url = url;
  }

  /** @override */
  async poll() {
    let health;
    try {
      health = await this._http.getJSON(this._url);
    } catch {
      return;
    }
    for (const [id, result] of Object.entries(health || {})) {
      this._setHealth(id, result.ok, result.text || "");
    }
  }
}
