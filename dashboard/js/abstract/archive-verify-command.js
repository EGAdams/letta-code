/**
 * Pure builder for the archive-verification terminal's shell command.
 *
 * `ls -a1` (one entry per line) piped through `awk`, which highlights the
 * exact archived file the server named in ANSI light-green so it is obvious
 * at a glance among any siblings in that folder. Shared by the Scanner tabs
 * (dashboard-boot.js) and the manual-entry form
 * (js/implementation/manual-entry-form.js) — both mount a terminal after a
 * document is stored and run this same command, so a human can visually
 * confirm a document landed where the server says it did, whether Mazda or
 * a manual save put it there.
 *
 * @param {string} archivePath  directory containing the archived file
 * @param {string} archiveName  the exact filename to highlight
 */
export function buildArchiveVerifyCommand(archivePath, archiveName) {
  const shellQuote = (value) => `'${String(value).replaceAll("'", `'"'"'`)}'`;
  return (
    `cd ${shellQuote(archivePath)} && ls -a1 | awk -v target=${shellQuote(archiveName)} ` +
    `'{ if ($0 == target) printf "\\033[102;30m%s\\033[0m\\n", $0; else print }'`
  );
}

/**
 * @typedef {Object} ArchivePathResult
 * @property {boolean} ok
 * @property {?string} archivePath   directory to `cd` into, only when ok
 * @property {?string} archiveName   the exact filename to highlight, only when ok
 * @property {?string} error         message to show, only when !ok
 */

/**
 * Boundary check for POST /api/scanner-archive-path's response: an HTTP
 * response is untrusted shape, not just untrusted value. Both call sites
 * (dashboard-boot.js's Scanner tabs and manual-entry-form.js, which fire
 * this same request right after a document is stored) used to read
 * `data.ok`/`data.archive_path`/`data.archive_name`/`data.error` inline,
 * duplicating the same boundary logic with no shape guarantee -- centralized
 * here so both stay in sync and a malformed/missing field can never produce
 * a `cd` into `undefined` or a blank highlight target.
 * @param {unknown} json
 * @returns {ArchivePathResult}
 */
export function readArchivePathResponse(json) {
  const blank = {
    ok: false,
    archivePath: null,
    archiveName: null,
    error: "archive path not found",
  };
  if (typeof json !== "object" || json === null) return blank;
  if (
    json.ok !== true ||
    typeof json.archive_path !== "string" ||
    !json.archive_path
  ) {
    return {
      ...blank,
      error: typeof json.error === "string" ? json.error : blank.error,
    };
  }
  return {
    ok: true,
    archivePath: json.archive_path,
    archiveName: typeof json.archive_name === "string" ? json.archive_name : "",
    error: null,
  };
}
