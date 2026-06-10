import { abstractMethod } from "./not-implemented.js";

/**
 * DetailRenderer — Strategy, and DetailRendererRegistry — its Context.
 *
 * The `DETAIL_RENDERERS` map dispatched an agent-detail tab id to a render
 * function (thoughts/messages/tool-calls → stream; chat-interface → chat). That
 * is a Strategy keyed by view id. Each strategy implements `render(target,
 * agentId)`; the registry is the Context that selects and runs one.
 */
export class DetailRenderer {
  /** Abstract: render this strategy's content into `target` for `agentId`. */
  render(_target, _agentId) {
    abstractMethod("render");
  }
}

/** Context that maps a view id → DetailRenderer strategy. */
export class DetailRendererRegistry {
  constructor() {
    this._strategies = new Map();
  }

  /** Register a strategy under a view id. Returns this for chaining. */
  register(viewId, strategy) {
    if (!(strategy instanceof DetailRenderer)) {
      throw new TypeError("strategy must be a DetailRenderer");
    }
    this._strategies.set(viewId, strategy);
    return this;
  }

  has(viewId) {
    return this._strategies.has(viewId);
  }

  /** Dispatch: run the strategy for `viewId`. Unknown ids are a silent no-op. */
  render(viewId, target, agentId) {
    const strategy = this._strategies.get(viewId);
    if (!strategy) return false;
    strategy.render(target, agentId);
    return true;
  }
}
