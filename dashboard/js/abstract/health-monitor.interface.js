import { abstractMethod } from "./not-implemented.js";

/**
 * HealthMonitor — Observer (Subject side).
 *
 * SM.pollHealth fetched /api/server-health then pushed the result into two
 * places: the main "Server Management" tab color and each per-server tab color.
 * That fan-out is the Observer pattern: the monitor is the Subject; tab
 * colorizers are Observers notified on every poll.
 *
 * `fetchHealth()` is the abstract primitive (the transport); `poll()` and the
 * subscribe/notify machinery are concrete and testable with a fake fetch.
 *
 * Health payload shape: { any_down: boolean, servers: [{key, status}] }
 * where status ∈ "up" | "down" | "starting" | "unknown".
 */
export class HealthMonitor {
  constructor() {
    this._observers = new Set();
    this.health = null;
  }

  /** Abstract: fetch the current health payload. */
  async fetchHealth() {
    abstractMethod("fetchHealth");
  }

  /** Register an observer fn(health). Returns an unsubscribe fn. */
  subscribe(observer) {
    this._observers.add(observer);
    return () => this._observers.delete(observer);
  }

  /** Notify every observer with the latest health. */
  notify() {
    for (const obs of this._observers) obs(this.health);
  }

  /**
   * Reduce a health payload to an overall status for the top-level tab:
   * any starting → "starting"; else any down → "down"; else any concern
   * (yellow "needs attention, fixable here") → "concern"; else "up".
   */
  static overallStatus(health) {
    if (!health) return "unknown";
    const servers = health.servers || [];
    if (servers.some((s) => s.status === "starting")) return "starting";
    if (health.any_down) return "down";
    if (health.any_concern || servers.some((s) => s.status === "concern")) {
      return "concern";
    }
    return "up";
  }

  /** Fetch + store + notify. Swallows transport errors (silent like original). */
  async poll() {
    try {
      this.health = await this.fetchHealth();
      this.notify();
    } catch {
      /* silent fail — keep last known health */
    }
  }
}
