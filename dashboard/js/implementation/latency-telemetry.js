/**
 * Global-backed adapters for ConversationLatencyObserverPort's dependencies.
 *
 * Same split as system-session-primitives.js: `abstract/` may not read
 * globals, so `performance` and `console` are bound here, and both are
 * injected rather than referenced directly so tests can drive them.
 */

export class PerformanceClock {
  /** @param {{ now(): number }} [perf] */
  constructor(perf = globalThis.performance) {
    this._perf = perf;
  }
  now() {
    return typeof this._perf?.now === "function"
      ? this._perf.now()
      : Date.now();
  }
}

export class ConsoleLatencySink {
  /** @param {Console} [target] */
  constructor(target = globalThis.console) {
    this._console = target;
  }
  publish(report) {
    this._console?.debug?.("[latency]", report);
  }
}

/**
 * Posts each report to /api/latency-log, which appends it to
 * dashboard/voice_latency.json (see voice/latency_log.py). Fire-and-forget:
 * a dropped report must never surface as a rejected promise or console noise
 * of its own, since ConversationLatencyObserver.finish() already treats sink
 * failures as non-fatal.
 */
export class HttpLatencySink {
  /** @param {import("../abstract/http-client.interface.js").HttpClient} http */
  constructor(http) {
    this._http = http;
  }
  publish(report) {
    this._http.postJSON("/api/latency-log", report).catch(() => {});
  }
}

/** Fan-out Composite so a report can reach more than one sink. */
export class CompositeLatencySink {
  /** @param {{ publish(report): void }[]} sinks */
  constructor(sinks) {
    this._sinks = sinks;
  }
  publish(report) {
    for (const sink of this._sinks) {
      try {
        sink.publish(report);
      } catch {
        // One sink's failure must not block the others.
      }
    }
  }
}
