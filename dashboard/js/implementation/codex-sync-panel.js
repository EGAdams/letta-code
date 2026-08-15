import { CodexSyncController } from "../abstract/codex-sync-controller.interface.js";

/**
 * DomCodexSyncController — the one concrete primitive CodexSyncController
 * needs: resolve an id against the real browser Document. Everything else
 * (polling, countdown tick, swap sequencing, rendering) lives in the
 * abstract base and is exercised there without a DOM.
 */
export class DomCodexSyncController extends CodexSyncController {
  constructor({
    http,
    doc = globalThis.document,
    setInterval: setIntervalFn,
  } = {}) {
    super({ http, setInterval: setIntervalFn });
    this._doc = doc;
  }

  _getElement(id) {
    return this._doc?.getElementById(id) ?? null;
  }
}
