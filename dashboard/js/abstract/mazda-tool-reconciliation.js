// mazda-tool-reconciliation.js — pure HTML for the System Status landing panel.
//
// This panel replaced the words "Select a section above", which told the
// operator nothing. What belongs on a status landing page is the answer to
// "does anything need running right now?", so that is what this renders: the
// standing agreement between the tools Mazda's MCP server serves and the tools
// its agent actually carries.
//
// The three states are deliberately distinct, because they call for different
// actions:
//
//   missing  — the agent cannot call tools its source defines. Red, and the
//              remediation command is shown ready to copy.
//   stale    — the agent carries tools the server no longer serves. They fail
//              at call time. Yellow; the same command detaches them.
//   agreed   — green, and the panel still lists what it checked, because a
//              green light with no evidence behind it is not worth trusting.
//
// Tools attached from *other* MCP servers are listed as context, never as a
// fault: `run_claude_code_sdk` and `executor_run` are supposed to be there.

import { TextUtils } from "./text-utils.js";

const esc = TextUtils.esc;

/** Which of the three states a reconciliation payload is in. */
export function reconciliationState(d) {
  if (!d || d.reachable === false) return "unreachable";
  if ((d.missing || []).length) return "missing";
  if ((d.stale || []).length) return "stale";
  return "agreed";
}

/** Does an operator have to go run something? */
export function needsAction(d) {
  const state = reconciliationState(d);
  return state === "missing" || state === "stale";
}

function toolList(names, className) {
  if (!names || !names.length) return "";
  const items = names
    .map((n) => `<li class="${className}"><code>${esc(n)}</code></li>`)
    .join("");
  return `<ul class="mtr-tools">${items}</ul>`;
}

function remediation(d) {
  if (!d.remediation) return "";
  return (
    '<p class="mtr-fix-label">Run this to reconcile:</p>' +
    `<pre class="mtr-fix"><code>${esc(d.remediation)}</code></pre>`
  );
}

export function renderMazdaToolReconciliation(d) {
  const state = reconciliationState(d);

  if (state === "unreachable") {
    return (
      '<div class="mtr-card mtr-bad"><h3>⚠ Mazda tool reconciliation</h3>' +
      `<p class="am-warn">${esc((d && d.text) || "no data")}</p>` +
      // Who failed to answer decides what the operator should go look at, so
      // the caller supplies that line. A dashboard serving a stale build 404s
      // its own route; saying "the Letta server" there sends them to the wrong
      // machine. Default to Letta because that is the common case.
      `<p class="am-dim">${esc(
        (d && d.hint) ||
          "Cannot tell whether Mazda's tools are in sync until the Letta server answers.",
      )}</p></div>`
    );
  }

  const served = d.served || [];
  const missing = d.missing || [];
  const stale = d.stale || [];
  const other = d.other_attached || [];

  let cls = "mtr-ok";
  let heading = `✓ Mazda tools in sync — ${served.length}/${served.length} attached`;
  let body = "";

  if (state === "missing") {
    cls = "mtr-bad";
    heading = `✗ Mazda is missing ${missing.length} of its ${served.length} tools`;
    body =
      "<p>These are served by the MCP server but not attached to the agent. " +
      "Mazda cannot call them:</p>" +
      toolList(missing, "mtr-missing") +
      remediation(d);
  } else if (state === "stale") {
    cls = "mtr-warn";
    heading = `⚠ ${stale.length} attached tool(s) are no longer served`;
    body =
      "<p>Attached to the agent but dropped from the MCP server. Calling one " +
      "fails at runtime:</p>" +
      toolList(stale, "mtr-stale") +
      remediation(d);
  } else {
    body =
      '<p class="am-dim">Nothing to run. Every tool the MCP server serves is ' +
      "attached to the agent.</p>";
  }

  let h = `<div class="mtr-card ${cls}"><h3>${esc(heading)}</h3>${body}`;
  h += `<details class="mtr-detail"><summary>What was checked (${served.length} tools)</summary>`;
  h += toolList(served, "mtr-served");
  if (other.length) {
    h +=
      '<p class="am-dim">Also attached, from other sources (not part of this ' +
      "check):</p>" +
      toolList(other, "mtr-other");
  }
  h += "</details>";
  h += `<p class="am-dim">Agent <code>${esc(d.agent_id || "")}</code> on <code>${esc(d.base_url || "")}</code></p>`;
  return h + "</div>";
}
