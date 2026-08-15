/**
 * The contract for one interface tab in a project workspace, plus its runtime
 * validator.
 *
 * The workspace is data-driven: adding an interface means adding one object of
 * this shape, never copying a page of HTML. That only works if a malformed spec
 * fails loudly instead of rendering a blank tab, so `validateInterfaceSpec`
 * checks the shape at the boundary where hand-written data enters the renderer.
 *
 * @typedef {object} Implementation
 * @property {string} name
 * @property {"current"|"planned"|"deprecated"} kind
 * @property {string} [file]      repo-relative path
 * @property {string} [note]
 *
 * @typedef {object} Diagram
 * @property {string} title
 * @property {string} code        Mermaid source
 * @property {string} [caption]
 *
 * @typedef {object} TestFile
 * @property {string} path
 * @property {number} [count]     number of test cases
 * @property {string} proves      what behaviour this file actually protects
 *
 * @typedef {object} InterfaceSpec
 * @property {string} id          URL slug, also the nav hash
 * @property {string} name        the interface's real name in the code
 * @property {string} [tagline]   one line shown under the heading
 * @property {string} status      one of Status
 * @property {string} [statusNote] one line qualifying the status pill
 * @property {string[]} responsibility  paragraphs: what job this owns
 * @property {{language?: string, code: string}} [contract]
 * @property {Implementation[]} [implementations]
 * @property {{dependsOn?: string[], usedBy?: string[], note?: string}} [dependencies]
 * @property {{done?: string[], gaps?: string[]}} [developmentStatus]
 * @property {{files?: TestFile[], untested?: string[], next?: string[]}} [tests]
 * @property {Diagram[]} [diagrams]
 * @property {{title: string, body: string}[]} [gotchas]  hard-won traps, kept
 *   next to the interface they bite, so the next person does not rediscover them
 * @property {string[]} [nextWork]
 * @property {{label: string, href: string}[]} [links]  shown under the heading
 */

/** The status vocabulary. `SUPERSEDED` covers code kept only as history. */
export const Status = Object.freeze({
  FINISHED: "finished",
  WORKING: "working",
  PARTIAL: "partial",
  PLANNED: "planned",
  BLOCKED: "blocked",
  REFACTOR: "refactor",
  SUPERSEDED: "superseded",
});

export const STATUS_LABELS = Object.freeze({
  [Status.FINISHED]: "Finished",
  [Status.WORKING]: "Working / Needs Testing",
  [Status.PARTIAL]: "Partial",
  [Status.PLANNED]: "Planned",
  [Status.BLOCKED]: "Blocked",
  [Status.REFACTOR]: "Needs Refactoring",
  [Status.SUPERSEDED]: "Superseded / History",
});

const VALID_KINDS = new Set(["current", "planned", "deprecated"]);
const SLUG = /^[a-z0-9][a-z0-9-]*$/;

/**
 * Throw on a malformed spec, returning it unchanged when it is usable.
 * @param {InterfaceSpec} spec
 * @returns {InterfaceSpec}
 */
export function validateInterfaceSpec(spec) {
  const fail = (why) => {
    throw new Error(`InterfaceSpec ${spec?.id ?? "(no id)"}: ${why}`);
  };
  if (!spec || typeof spec !== "object") fail("must be an object");
  if (typeof spec.id !== "string" || !SLUG.test(spec.id))
    fail("id must be a lowercase slug");
  if (typeof spec.name !== "string" || !spec.name.trim()) fail("name required");
  if (!STATUS_LABELS[spec.status])
    fail(`status must be one of ${Object.values(Status).join(", ")}`);
  if (!Array.isArray(spec.responsibility) || !spec.responsibility.length)
    fail("responsibility must be a non-empty array of paragraphs");

  for (const impl of spec.implementations || []) {
    if (!impl?.name) fail("every implementation needs a name");
    if (!VALID_KINDS.has(impl.kind))
      fail(
        `implementation ${impl.name}: kind must be current/planned/deprecated`,
      );
  }
  for (const diagram of spec.diagrams || []) {
    if (!diagram?.title || !diagram?.code)
      fail("every diagram needs a title and Mermaid code");
  }
  for (const file of spec.tests?.files || []) {
    if (!file?.path || !file?.proves)
      fail("every test file needs a path and what it proves");
  }
  for (const gotcha of spec.gotchas || []) {
    if (!gotcha?.title || !gotcha?.body)
      fail("every gotcha needs a title and a body");
  }
  for (const link of spec.links || []) {
    if (!link?.label || !link?.href) fail("every link needs a label and href");
    // Same-origin paths only: these pages are served from the dashboard and a
    // spec is hand-written data, not a place to introduce arbitrary targets.
    if (!link.href.startsWith("/"))
      fail(`link ${link.label} must be a root-relative path`);
  }
  return spec;
}

/** Validate a whole workspace, and reject duplicate ids. */
export function validateSpecs(specs) {
  if (!Array.isArray(specs) || !specs.length)
    throw new Error("a workspace needs at least one InterfaceSpec");
  const seen = new Set();
  for (const spec of specs) {
    validateInterfaceSpec(spec);
    if (seen.has(spec.id)) throw new Error(`duplicate spec id: ${spec.id}`);
    seen.add(spec.id);
  }
  return specs;
}
