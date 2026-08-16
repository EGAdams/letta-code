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
