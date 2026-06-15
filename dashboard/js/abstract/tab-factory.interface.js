import { abstractMethod } from "./not-implemented.js";

/**
 * TabFactory — Factory Method.
 *
 * Agent tabs and server tabs were both built by hand with createElement +
 * className + dataset assignments. The shape is identical apart from which
 * data-* attributes get set, so tab creation is a Factory Method:
 * `createElement()` is the abstract product-creation step, while `buildAgentTab`
 * / `buildServerTab` are concrete factory methods that configure the product.
 *
 * The element port must expose at least: { className, textContent, type,
 * dataset:{} } — a real DOM element satisfies this, and so does a plain test
 * double, so the configuration logic is unit-testable without a browser.
 */
export class TabFactory {
  /** Abstract: create a fresh element to be configured into a tab. */
  createElement() {
    abstractMethod("createElement");
  }

  _baseTab(label, extraClass = "") {
    const el = this.createElement();
    el.type = "button";
    el.className = `tab${extraClass ? ` ${extraClass}` : ""}`;
    el.textContent = label;
    return el;
  }

  /** Factory method: a sidebar tab for an agent {id, name}. */
  buildAgentTab(agent) {
    const el = this._baseTab(agent.name, "agent-tab");
    el.dataset.nav = "agents";
    el.dataset.agentId = agent.id;
    el.dataset.agentName = agent.name;
    return el;
  }

  /** Factory method: a sidebar tab for a server {key, name}. */
  buildServerTab(server) {
    const el = this._baseTab(server.name);
    el.dataset.serverKey = server.key;
    el.dataset.serverName = server.name;
    return el;
  }

  /** Factory method: a sidebar tab for an SSH connection {key, name}. */
  buildConnectionTab(conn) {
    const el = this._baseTab(conn.name);
    el.dataset.connKey = conn.key;
    el.dataset.connName = conn.name;
    return el;
  }
}
