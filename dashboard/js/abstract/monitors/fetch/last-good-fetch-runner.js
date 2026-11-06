import { IFetchRunner } from "./fetch-runner.interface.js";

/**
 * Decorator: when a fetch fails, hand back the last good payload marked
 * `{ stale: true, stale_error }` so a card greys out instead of going blank.
 * With nothing cached the failure propagates.
 */
export class LastGoodFetchRunner extends IFetchRunner {
  constructor(inner) {
    super();
    this.inner = inner;
    this._lastGood = new Map();
  }

  async run(url) {
    try {
      const payload = await this.inner.run(url);
      this._lastGood.set(url, payload);
      return payload;
    } catch (error) {
      if (!this._lastGood.has(url)) throw error;
      const last = this._lastGood.get(url);
      if (last === null || typeof last !== "object" || Array.isArray(last))
        return last;
      return { ...last, stale: true, stale_error: error.message };
    }
  }
}
