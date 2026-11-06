/** customElements.define, tolerating a second boot of the same module. */
export function defineOnce(tag, elementClass) {
  if (!customElements.get(tag)) customElements.define(tag, elementClass);
}
