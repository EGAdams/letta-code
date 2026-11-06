import { IFetchRunner } from "./fetch-runner.interface.js";

/** Decorator: callers asking for a URL already in flight share one request. */
export class DedupFetchRunner extends IFetchRunner {
  constructor(inner) {
    super();
    this.inner = inner;
    this._inFlight = new Map();
  }

  run(url) {
    if (this._inFlight.has(url)) return this._inFlight.get(url);
    const pending = Promise.resolve()
      .then(() => this.inner.run(url))
      .finally(() => this._inFlight.delete(url));
    this._inFlight.set(url, pending);
    return pending;
  }
}
