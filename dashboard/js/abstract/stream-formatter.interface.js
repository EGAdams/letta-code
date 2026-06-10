import { abstractMethod } from "./not-implemented.js";
import { TextUtils } from "./text-utils.js";

/**
 * StreamFormatter — Strategy.
 *
 * `formatStreamRow()` turned a {date,type,text} record into one HTML `.msi-entry`.
 * Different streams (agent thoughts vs. server logs) may eventually want
 * different formatting, so the row→HTML mapping is a Strategy: subclasses
 * override `formatRow()`.
 *
 * `AgentStreamFormatter` below is the concrete strategy matching the original
 * behavior. It is included here (not in implementation/) because it is pure
 * string logic with no DOM dependency, making it directly testable.
 */
export class StreamFormatter {
  /** Abstract: map a row record to an HTML string. */
  formatRow(_row) {
    abstractMethod("formatRow");
  }

  /** Build a stable dedup key from a row. Shared default policy. */
  keyFor(row) {
    return `${row.date || ""}|${row.type || ""}|${String(row.text || "").slice(0, 120)}`;
  }
}

/** Concrete Strategy reproducing the original formatStreamRow() output. */
export class AgentStreamFormatter extends StreamFormatter {
  formatRow(row) {
    const stamp = (row.date || "").replace("T", " ").slice(0, 19);
    const type = TextUtils.esc((row.type || "").replace("_message", ""));
    const { header, rest } = TextUtils.splitLeadingHeader(row.text);

    let body;
    if (header) {
      body = `<span class="hdr">${TextUtils.esc(header)}</span> ${TextUtils.esc(rest)}`;
    } else if (type) {
      body = `<span class="hdr">${type}</span> ${TextUtils.esc(rest)}`;
    } else {
      body = TextUtils.esc(rest);
    }
    return `<div class="msi-entry"><span class="msi-stamp">[${stamp}]</span> ${body}</div>`;
  }
}
