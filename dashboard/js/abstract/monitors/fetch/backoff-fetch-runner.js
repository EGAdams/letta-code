import { IFetchRunner } from "./fetch-runner.interface.js";

/**
 * Decorator: after a failure, refuse that URL for a while instead of hammering
 * it — doubling from `baseMs` to `maxMs`. A 404 waits `notFoundMs` (the-factory
 * waited an hour: the route will not appear by itself).
 */
export class BackoffFetchRunner extends IFetchRunner {
  constructor(
    inner,
    {
      baseMs = 5000,
      maxMs = 300000,
      notFoundMs = 3600000,
      now = Date.now,
    } = {},
  ) {
    super();
    Object.assign(this, { inner, baseMs, maxMs, notFoundMs, now });
    this._state = new Map();
  }

  async run(url) {
    const state = this._state.get(url);
    if (state && this.now() < state.until) {
      throw new Error(`backing off (${state.reason})`);
    }
    try {
      const payload = await this.inner.run(url);
      this._state.delete(url);
      return payload;
    } catch (error) {
      const failures = (state?.failures || 0) + 1;
      const wait = /HTTP 404/.test(error.message)
        ? this.notFoundMs
        : Math.min(this.maxMs, this.baseMs * 2 ** (failures - 1));
      this._state.set(url, {
        failures,
        until: this.now() + wait,
        reason: error.message,
      });
      throw error;
    }
  }
}
