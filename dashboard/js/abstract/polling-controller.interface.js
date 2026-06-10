import { abstractMethod } from "./not-implemented.js";

/**
 * PollingController — Template Method.
 *
 * Both AM.renderStream and SM.openServer/pollHealth share the same skeleton:
 *   stopPoll(); await poll(); timer = setInterval(poll, ms)
 * with a guard that a poll for a stale target is a no-op.
 *
 * The skeleton (start/stop/lifecycle) is concrete here; the actual work is the
 * abstract `poll()` primitive. The scheduler (setInterval/clearInterval) is
 * injected so tests can drive ticks deterministically instead of waiting on
 * real timers.
 */
export class PollingController {
  /**
   * @param {object} [opts]
   * @param {number} [opts.intervalMs=3000]
   * @param {(fn:Function,ms:number)=>any} [opts.setInterval]
   * @param {(handle:any)=>void} [opts.clearInterval]
   */
  constructor({
    intervalMs = 3000,
    setInterval: setIntervalFn = globalThis.setInterval,
    clearInterval: clearIntervalFn = globalThis.clearInterval,
  } = {}) {
    this.intervalMs = intervalMs;
    this._setInterval = setIntervalFn;
    this._clearInterval = clearIntervalFn;
    this._timer = null;
  }

  /** Abstract: do one unit of polling work. Override in implementation. */
  async poll() {
    abstractMethod("poll");
  }

  /** True while a recurring timer is armed. */
  get isPolling() {
    return this._timer !== null;
  }

  /** Stop any existing loop, run one immediate poll, then arm the interval. */
  async start() {
    this.stop();
    await this.poll();
    this._timer = this._setInterval(() => this.poll(), this.intervalMs);
  }

  /** Cancel the recurring timer. Safe to call when not polling. */
  stop() {
    if (this._timer !== null) {
      this._clearInterval(this._timer);
      this._timer = null;
    }
  }
}
