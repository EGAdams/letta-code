/**
 * PollScheduler — refreshes every source now and then every `intervalMs`,
 * but only while `isActive()` says the page is being looked at. Timers are
 * injectable for tests.
 */
export class PollScheduler {
  constructor(
    sources,
    {
      intervalMs = 15000,
      isActive = () => true,
      // Bound: browsers throw "Illegal invocation" when these run with
      // `this` set to a plain object.
      timers = {
        setInterval: globalThis.setInterval.bind(globalThis),
        clearInterval: globalThis.clearInterval.bind(globalThis),
      },
    } = {},
  ) {
    Object.assign(this, { sources, intervalMs, isActive, timers });
    this._handle = null;
  }

  tick() {
    if (!this.isActive()) return Promise.resolve([]);
    return Promise.allSettled(this.sources.map((s) => s.refresh()));
  }

  start() {
    if (this._handle !== null) return;
    this.tick();
    this._handle = this.timers.setInterval(() => this.tick(), this.intervalMs);
  }

  stop() {
    if (this._handle === null) return;
    this.timers.clearInterval(this._handle);
    this._handle = null;
  }
}
