import { TabFactory } from "../abstract/tab-factory.interface.js";

/**
 * DomTabFactory — concrete TabFactory that produces real `<button>` elements.
 *
 * The factory methods (buildAgentTab / buildServerTab) and their dataset/class
 * configuration live in the base class; this only binds the product-creation
 * step `createElement()` to `document.createElement('button')`.
 */
export class DomTabFactory extends TabFactory {
  /** @param {Document} [doc] */
  constructor(doc = globalThis.document) {
    super();
    this._doc = doc;
  }

  /** @override */
  createElement() {
    return this._doc.createElement("button");
  }
}
