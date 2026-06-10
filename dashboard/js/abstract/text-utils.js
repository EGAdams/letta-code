/**
 * TextUtils — pure, dependency-free helpers shared across the dashboard.
 *
 * These were inlined as the `esc()` / `sleep()` functions and the markdown
 * stripping inside `Speech.clean()`. They are pure (no DOM, no I/O), so they
 * live as static methods and are fully unit-testable on their own.
 */
// biome-ignore lint/complexity/noStaticOnlyClass: namespacing pure helpers for clarity at call sites
export class TextUtils {
  /** HTML-escape a value for safe innerHTML insertion. Mirrors the old esc(). */
  static esc(s) {
    return String(s == null ? "" : s).replace(
      /[&<>"]/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c],
    );
  }

  /** Promise that resolves after `ms`. Mirrors the old sleep(). */
  static sleep(ms, scheduler = setTimeout) {
    return new Promise((resolve) => scheduler(resolve, ms));
  }

  /** Strip markdown emphasis so text-to-speech reads cleanly. */
  static stripMarkdown(text) {
    return String(text || "")
      .replace(/\*\*/g, "")
      .replace(/[`#_>]/g, "")
      .trim();
  }

  /**
   * Pull a leading "**Header**" out of a stream row's text, if present.
   * Returns { header, rest } where header may be null.
   */
  static splitLeadingHeader(text) {
    const str = String(text || "");
    const m = str.match(/^\*\*(.+?)\*\*\s*/);
    if (!m) return { header: null, rest: str.replace(/\*\*/g, "") };
    return { header: m[1], rest: str.slice(m[0].length).replace(/\*\*/g, "") };
  }
}
