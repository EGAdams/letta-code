/**
 * ComponentBase — the lifecycle every the-factory component template repeats:
 * constructed with (shadow root, host element); attributes land on `this`
 * camelCased. Subclasses override only what they use.
 */
export const camelCase = (name) =>
  name.replace(/-([a-z])/g, (_, c) => c.toUpperCase());

export class ComponentBase {
  constructor($el, $host) {
    this.$el = $el;
    this.$host = $host;
  }

  connectedCallback() {}
  disconnectedCallback() {}
  adoptedCallback() {}

  attributeChangedCallback(name, _oldValue, newValue) {
    this[camelCase(name)] = newValue;
    this.render?.();
  }
}
