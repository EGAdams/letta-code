/**
 * Every response reader must fail SAFE, never optimistic.
 *
 * The browser half of property_tests/test_boundary_readers_fail_safe.py, and
 * the same lesson. Four defects on 2026-08-19 were one defect wearing four
 * hats: code reading data from outside itself answered the *convenient* thing
 * when the data was absent, garbled, or not the shape it expected. A dispatch
 * that was rejected with HTTP 429 read as delivered; the string "maybe"
 * switched paid reading on; a model's real answer was reported as an unrelated
 * model's quota error.
 *
 * Nothing type-checks a fetch response in vanilla JS. These readers ARE the
 * type check, which makes them the exact place that class of bug lands -- and
 * `readMazdaModeResponse` in particular decides what a physical switch on the
 * page claims about a mode the server may not be in.
 *
 * Adding a reader is one line in READERS. The next one gets this sweep free,
 * and the failure this file exists to catch is the one an author does not
 * anticipate.
 */
import { describe, expect, test } from "bun:test";
import { readArchivePathResponse } from "../abstract/archive-verify-command.js";
import {
  readEditResponse,
  readSearchResponse,
} from "../abstract/expense-edit.interface.js";
import {
  readArchivePreviewResponse,
  readCategoriesResponse,
  readPrefillResponse,
  readSubmitResponse,
  readVendorKeysResponse,
  readVendorRememberedResponse,
} from "../abstract/manual-entry.interface.js";
import { readMazdaFillResponse } from "../abstract/mazda-fill.interface.js";
import {
  readMazdaModeDataset,
  readMazdaModeResponse,
} from "../abstract/mazda-mode.interface.js";
import {
  readStatementBreakupResponse,
  readStatementEntryResponse,
} from "../abstract/statement-breakup.interface.js";

/**
 * Everything a boundary hands back when something upstream has gone wrong: a
 * dead server, a truncated body, a schema change, a proxy serving HTML, a
 * field renamed, JSON.parse handed something that wasn't JSON.
 */
const HOSTILE_INPUTS = [
  null,
  undefined,
  {},
  [],
  "",
  " ",
  0,
  1,
  -1,
  true,
  false,
  Number.NaN,
  Number.POSITIVE_INFINITY,
  "null",
  "true",
  "maybe",
  "ok",
  "<html>502 Bad Gateway</html>",
  [null],
  [{}],
  [{ unexpected: "shape" }],
  { ok: "yes" },
  { ok: 1 },
  { ok: "true" },
  { error: null },
  { transactions: null },
  { transactions: "nope" },
  { transactions: {} },
  { statement: "nope" },
  { receipt: "nope" },
  { mode: null },
  { mode: "semi" },
  { mode: "auto" }, // a mode with no ok: never a confirmed change
  { automatic: true }, // ditto -- the flag alone is not an answer
  { shape: "many-expenses" }, // shape with nothing behind it
];

/**
 * Each entry: [name, verdict, theAnswerThatWouldBeALie].
 * `verdict` returns the reader's optimistic claim as a boolean.
 */
const READERS = [
  ["readMazdaModeResponse.ok", (v) => readMazdaModeResponse(v).ok, true],
  [
    // The switch's position must only ever come from a confirmed answer. One
    // showing a mode the server is not in is worse than one that visibly
    // refused to move: the operator walks away believing Mazda is on.
    "readMazdaModeResponse claims Automatic",
    (v) => {
      const state = readMazdaModeResponse(v);
      return state.ok && state.automatic;
    },
    true,
  ],
  ["readMazdaFillResponse.ok", (v) => readMazdaFillResponse(v).ok, true],
  [
    // A statement shown as one expense silently discards every transaction but
    // one. Junk must land on the recoverable shape, never this one.
    "readMazdaFillResponse claims MANY expenses with no rows",
    (v) => {
      const result = readMazdaFillResponse(v);
      return result.shape === "many-expenses" && result.items.length === 0
        ? result.ok
        : false;
    },
    true,
  ],
  [
    "readStatementBreakupResponse.ok",
    (v) => readStatementBreakupResponse(v).ok,
    true,
  ],
  [
    "readStatementBreakupResponse invents rows",
    (v) => readStatementBreakupResponse(v).items.length > 0,
    true,
  ],
  ["readPrefillResponse.ok", (v) => readPrefillResponse(v).ok, true],
  [
    // Python stamps the switch's starting position into the mount point. A
    // dataset we cannot read must fall back to a stated default, not to
    // whatever the last truthy attribute happened to be.
    "readMazdaModeDataset claims an operator choice",
    (v) => readMazdaModeDataset(v).source === "operator",
    true,
  ],

  // The rest of the intake path's readers. Added when the completeness guard
  // below found them unswept -- which is the guard doing exactly its job.
  ["readSubmitResponse.ok", (v) => readSubmitResponse(v).ok, true],
  [
    "readStatementEntryResponse.ok",
    (v) => readStatementEntryResponse(v).ok,
    true,
  ],
  [
    // Counts drive the "2 stored, 1 already on file" sentence. Inventing one
    // from a malformed response tells the operator work happened that didn't.
    "readStatementEntryResponse invents a stored count",
    (v) => readStatementEntryResponse(v).stored > 0,
    true,
  ],
  [
    "readArchivePreviewResponse.ok",
    (v) => readArchivePreviewResponse(v).ok,
    true,
  ],
  ["readArchivePathResponse.ok", (v) => readArchivePathResponse(v).ok, true],
  ["readSearchResponse.ok", (v) => readSearchResponse(v).ok, true],
  [
    // A search result the operator can click becomes an expense they edit.
    "readSearchResponse invents records",
    (v) => readSearchResponse(v).records.length > 0,
    true,
  ],
  ["readEditResponse.ok", (v) => readEditResponse(v).ok, true],
  [
    // These fill a <select>. A junk response must leave it empty rather than
    // offering a vendor key that does not exist.
    "readVendorKeysResponse invents vendors",
    (v) => readVendorKeysResponse(v).length > 0,
    true,
  ],
  [
    "readCategoriesResponse invents categories",
    (v) => readCategoriesResponse(v).length > 0,
    true,
  ],
  [
    // The claim that matters is `remembered`, not whether an object came back:
    // this reader returns a filled-in "nothing was remembered" for any object,
    // which is the safe answer. Only a positive flag says the server stored a
    // vendor mapping, and junk must never produce one.
    "readVendorRememberedResponse claims something was remembered",
    (v) => (readVendorRememberedResponse(v) || {}).remembered === true,
    true,
  ],
];

describe("no boundary reader can be talked into the optimistic answer", () => {
  for (const [name, verdict, unsafe] of READERS) {
    for (const value of HOSTILE_INPUTS) {
      test(`${name} — ${JSON.stringify(value) ?? String(value)}`, () => {
        expect(verdict(value)).not.toBe(unsafe);
      });
    }
  }
});

describe("no boundary reader throws on hostile input", () => {
  // A reader that throws takes down the handler that was going to report the
  // real problem. Every one of these runs on an error path already.
  for (const [name, verdict] of READERS) {
    for (const value of HOSTILE_INPUTS) {
      test(`${name} — ${JSON.stringify(value) ?? String(value)}`, () => {
        expect(() => verdict(value)).not.toThrow();
      });
    }
  }
});

describe("readers return their declared shape whatever arrives", () => {
  // A caller reading `.items.length` or `.header.bankName` off a reader's
  // result must never hit undefined, however malformed the response was.
  for (const value of HOSTILE_INPUTS) {
    test(`readMazdaFillResponse — ${JSON.stringify(value) ?? String(value)}`, () => {
      const result = readMazdaFillResponse(value);
      expect(Array.isArray(result.items)).toBe(true);
      expect(Array.isArray(result.excludedRows)).toBe(true);
      expect(Array.isArray(result.missingFields)).toBe(true);
      expect(typeof result.shape).toBe("string");
      expect(typeof result.model).toBe("string");
      expect(typeof result.rereadAfter).toBe("string");
      expect(result.header).toBeDefined();
      expect(result.prefill).toBeDefined();
    });

    test(`readMazdaModeResponse — ${JSON.stringify(value) ?? String(value)}`, () => {
      const state = readMazdaModeResponse(value);
      expect(typeof state.ok).toBe("boolean");
      expect(typeof state.automatic).toBe("boolean");
      expect(typeof state.mode).toBe("string");
      expect(typeof state.label).toBe("string");
    });
  }
});

describe("the sweep stays complete as readers are added", () => {
  // The point of this file is the case nobody anticipated, which is worthless
  // if the next boundary reader is simply never added to READERS. This fails
  // the moment one exists that the sweep does not cover.
  test("every read*Response export in js/abstract is swept", async () => {
    const { readdirSync, readFileSync } = await import("node:fs");
    const { join } = await import("node:path");
    const abstractDir = join(import.meta.dir, "..", "abstract");
    // Coverage is read from the READERS registry, NOT from this file's source
    // text. A first attempt matched the whole file, so an `import` line counted
    // as coverage and a reader could be imported, never swept, and still pass.
    const swept = READERS.map(([name]) => name);

    const exported = [];
    for (const file of readdirSync(abstractDir)) {
      if (!file.endsWith(".js")) continue;
      const source = readFileSync(join(abstractDir, file), "utf8");
      for (const match of source.matchAll(
        /export function (read\w*Response)\b/g,
      )) {
        exported.push(match[1]);
      }
    }

    expect(exported.length).toBeGreaterThan(0);
    const unswept = exported.filter(
      (name) => !swept.some((entry) => entry.includes(name)),
    );
    expect(unswept).toEqual([]);
  });
});
