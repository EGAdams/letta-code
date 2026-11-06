#!/usr/bin/env bun
// new-component.js — the-factory's scripts/newComponent.js for this dashboard.
// Usage (from dashboard/): bun js/components/component-kit/new-component.js my-widget
// Writes js/components/my-widget/ with index, component, observed-attributes,
// html and styles/{main,_variables,_modifiers}.css. Refuses to overwrite.
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const kebab = (process.argv[2] || "").trim().toLowerCase();
if (!/^[a-z][a-z0-9]*(-[a-z0-9]+)+$/.test(kebab)) {
  console.error("usage: new-component.js <kebab-name-with-a-dash>");
  process.exit(2);
}
const pascal = kebab
  .split("-")
  .map((w) => w[0].toUpperCase() + w.slice(1))
  .join("");
const camel = pascal[0].toLowerCase() + pascal.slice(1);
const dir = join(import.meta.dir, "..", kebab);
if (existsSync(dir)) {
  console.error(`${dir} already exists`);
  process.exit(1);
}

const files = {
  [`${kebab}.component.js`]: `import { Component } from "../component-kit/component.js";
import { ComponentBase } from "../component-kit/component-base.js";

/** <${kebab}> — describe what it shows. */
export const ${pascal} = Component({
  html: new URL("./${kebab}.html", import.meta.url).href,
  style: new URL("./styles/main.css", import.meta.url).href,
  properties: [],
})(class ${pascal} extends ComponentBase {
  constructor($el, $host) {
    super($el, $host);
  }
});
`,
  [`${kebab}.observed-attributes.js`]: `/** Attributes <${kebab}> forwards to its component. */
export const observedAttributes${pascal} = Object.freeze([]);

/** Element properties proxied to the component instance. */
export const properties${pascal} = Object.freeze([]);
`,
  "index.js": `import { defineOnce } from "../component-kit/define-once.js";
import { wrap } from "../component-kit/wrap.js";
import { observedAttributes${pascal}, properties${pascal} } from "./${kebab}.observed-attributes.js";

export const ${camel}Define = () =>
  defineOnce("${kebab}", wrap(() => import("./${kebab}.component.js"), "${pascal}", observedAttributes${pascal}, properties${pascal}));
`,
  [`${kebab}.html`]: `<div class="${kebab}"></div>\n`,
  "styles/main.css": `@import "./_variables.css";\n@import "./_modifiers.css";\n`,
  "styles/_variables.css": `/* <${kebab}> tokens. */\n:host { display: block; }\n`,
  "styles/_modifiers.css": `/* <${kebab}> modifiers: state classes and host attributes. */\n`,
};

mkdirSync(join(dir, "styles"), { recursive: true });
for (const [name, text] of Object.entries(files)) {
  writeFileSync(join(dir, name), text);
  console.log(`Created ${join(dir, name)}`);
}
