import { ChatGptProviderAccountController } from "../abstract/chatgpt-provider-account-controller.interface.js";

/**
 * DomChatGptProviderAccountController — the one concrete primitive
 * ChatGptProviderAccountController needs: resolve an id against the real
 * browser Document. Everything else (refresh/set sequencing, rendering)
 * lives in the abstract base and is exercised there without a DOM.
 */
export class DomChatGptProviderAccountController extends ChatGptProviderAccountController {
  constructor({ http, doc = globalThis.document, setInterval } = {}) {
    super({ http, setInterval });
    this._doc = doc;
  }

  _getElement(id) {
    return this._doc?.getElementById(id) ?? null;
  }
}
