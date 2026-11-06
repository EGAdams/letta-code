import { templateLoader } from "./template-loader.js";

/**
 * wrap() — the-factory's custom-element wrapper: open shadow root, lazy
 * import of the component class, construction as (shadow, host), attribute
 * replay, property proxies, and a 'ready' event. `properties` are proxied
 * from the element to the instance, queued until the instance exists.
 */
export function wrap(
  importComponent,
  className,
  observedAttributes = [],
  properties = [],
  loader = templateLoader,
) {
  return class extends HTMLElement {
    static get observedAttributes() {
      return observedAttributes;
    }

    constructor() {
      super();
      const shadow = this.attachShadow({ mode: "open" });
      this._pending = {};
      for (const name of properties) {
        Object.defineProperty(this, name, {
          get: () =>
            this._instance ? this._instance[name] : this._pending[name],
          set: (value) => {
            if (this._instance) this._instance[name] = value;
            else this._pending[name] = value;
          },
        });
      }
      this.ready = importComponent()
        .then(async (module) => {
          const Ctor = module[className];
          shadow.innerHTML = await loader.html(Ctor.prototype.sourceHtmlUrl);
          if (Ctor.prototype.sourceStyleUrl) {
            shadow.insertBefore(
              loader.styleNode(document, Ctor.prototype.sourceStyleUrl),
              shadow.firstChild,
            );
          }
          this._instance = new Ctor(shadow, this);
          for (const name of observedAttributes) {
            if (this.hasAttribute(name))
              this._instance.attributeChangedCallback(
                name,
                null,
                this.getAttribute(name),
              );
          }
          Object.assign(this._instance, this._pending);
          if (this._connected) this._instance.connectedCallback();
          this.dispatchEvent(new Event("ready"));
          return this._instance;
        })
        .catch((error) =>
          console.error(`[${className}] failed to load:`, error),
        );
    }

    connectedCallback() {
      this._connected = true;
      this._instance?.connectedCallback();
    }
    disconnectedCallback() {
      this._connected = false;
      this._instance?.disconnectedCallback();
    }
    adoptedCallback() {
      this._instance?.adoptedCallback();
    }

    attributeChangedCallback(name, oldValue, newValue) {
      this._instance?.attributeChangedCallback(name, oldValue, newValue);
    }
  };
}
