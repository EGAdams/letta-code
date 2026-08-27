import { Clock, IdSource } from "../abstract/session-clock.js";

/**
 * The global-backed halves of the session primitives.
 *
 * `abstract/` is not allowed to read globals, so `Date` and `crypto` are bound
 * here — the same split as every other interface in this directory. Both are
 * injected rather than referenced directly so a test can drive them, and both
 * degrade instead of throwing: an environment without `crypto.randomUUID`
 * (older WebViews, a plain Node run) still gets unique-enough ids.
 */

export class SystemClock extends Clock {
  /** @param {() => number} [now] */
  constructor(now = () => Date.now()) {
    super();
    this._now = now;
  }
  now() {
    return this._now();
  }
}

export class RandomIdSource extends IdSource {
  /** @param {Crypto} [cryptoObj] */
  constructor(cryptoObj = globalThis.crypto) {
    super();
    this._crypto = cryptoObj;
    this._counter = 0;
  }
  next(prefix = "id") {
    return `${prefix}-${this._token()}`;
  }
  /** @private */
  _token() {
    if (typeof this._crypto?.randomUUID === "function") {
      return this._crypto.randomUUID();
    }
    // Fallback: a counter plus the clock. Uniqueness within one page is all a
    // generation id needs — these ids never leave the browser.
    this._counter += 1;
    return `${Date.now().toString(36)}${this._counter.toString(36)}`;
  }
}
