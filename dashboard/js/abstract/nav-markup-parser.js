// nav-markup-parser.js — pure string parsing of the top-level sidebar (and its
// view sections) out of a fetched dashboard.html document.
//
// No DOM: a page fetched over the wire is just a string, and the live-sync
// poll (implementation/dom-nav-live-sync.js) needs to compare "what's in this
// markup" against "what's on screen" before touching the real document. Pure
// regex parsing keeps that comparison unit-testable in Node and independent
// of whatever DOM happens to be available.

const NAV_MAIN_RE = /<nav id="nav-main">([\s\S]*?)<\/nav>/;
const BUTTON_RE = /<button([^>]*)>([\s\S]*?)<\/button>/g;
const SECTION_RE = /<section([^>]*)>([\s\S]*?)<\/section>/g;
const ATTR_RE = /([a-zA-Z-]+)="([^"]*)"/g;

function parseAttrs(attrString) {
  const attrs = {};
  ATTR_RE.lastIndex = 0;
  for (const m of (attrString || "").matchAll(ATTR_RE)) {
    attrs[m[1]] = m[2];
  }
  return attrs;
}

/** The raw markup between `<nav id="nav-main">` and its closing tag. */
export function parseNavMainMarkup(html) {
  const match = NAV_MAIN_RE.exec(html || "");
  return match ? match[1] : "";
}

/**
 * Every top-level `data-nav="main"` tab in document order, deduplicated by
 * `data-target` (a repeated target in the markup keeps only the first).
 * @returns {{target: string, label: string}[]}
 */
export function parseNavMainTabs(html) {
  const inner = parseNavMainMarkup(html);
  const tabs = [];
  const seen = new Set();
  BUTTON_RE.lastIndex = 0;
  for (const m of inner.matchAll(BUTTON_RE)) {
    const attrs = parseAttrs(m[1]);
    const target = attrs["data-nav"] === "main" ? attrs["data-target"] : null;
    if (!target || seen.has(target)) continue;
    seen.add(target);
    tabs.push({ target, label: m[2].replace(/<[^>]+>/g, "").trim() });
  }
  return tabs;
}

/**
 * The `<section id="target" class="...">` view for a given nav target, as
 * structured data rather than raw markup — a browser's real `innerHTML`
 * setter parses `innerHTML` back into nodes, so the caller never needs to
 * walk the fragment itself.
 * @returns {{id: string, className: string, innerHTML: string} | null}
 */
export function parseViewSection(html, target) {
  SECTION_RE.lastIndex = 0;
  for (const m of (html || "").matchAll(SECTION_RE)) {
    const attrs = parseAttrs(m[1]);
    if (attrs.id === target) {
      return { id: target, className: attrs.class || "view", innerHTML: m[2] };
    }
  }
  return null;
}
