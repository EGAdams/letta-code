import { HealthMonitor } from "../abstract/health-monitor.interface.js";

/**
 * ServerHealthMonitor — concrete HealthMonitor whose transport is an HttpClient
 * hitting `/api/server-health`. The observer fan-out (subscribe / notify / poll)
 * and the `overallStatus` reducer are inherited; this only binds `fetchHealth`.
 *
 * Tab colorizers register via `subscribe(health => …)` and are notified on each
 * poll — reproducing the original `updateMainTabColor` / `updateServerTabColors`
 * fan-out without coupling the monitor to the DOM.
 */
export class ServerHealthMonitor extends HealthMonitor {
  /**
   * @param {import("../abstract/http-client.interface.js").HttpClient} http
   * @param {string} [endpoint]
   */
  constructor(http, endpoint = "/api/server-health") {
    super();
    if (!http || typeof http.getJSON !== "function") {
      throw new Error("ServerHealthMonitor requires an HttpClient");
    }
    this._http = http;
    this._endpoint = endpoint;
  }

  /** @override */
  async fetchHealth() {
    return this._http.getJSON(this._endpoint);
  }
}
