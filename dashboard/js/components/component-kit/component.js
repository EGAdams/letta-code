/**
 * Component(meta) — the-factory's @Component decorator, called as a function
 * because there is no build step: `export const X = Component({...})(class X {})`.
 * html and style are URLs (resolve them with import.meta.url), not inlined text.
 */
export function Component(meta = {}) {
  return (target) => {
    target.prototype.sourceHtmlUrl = meta.html || "";
    target.prototype.sourceStyleUrl = meta.style || "";
    target.prototype.properties = meta.properties || [];
    return target;
  };
}
