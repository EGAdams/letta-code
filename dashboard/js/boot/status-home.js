// status-home.js — the System Status landing page.
//
// Opening System Status used to show "Select a section above". That is a
// prompt, not a status: the one page named for telling you the system's state
// told you nothing about it. It now runs Mazda's tool reconciliation on open
// and reports whether anything needs running.
//
// Fetched on open rather than polled. This is a landing panel an operator
// looks at deliberately, and the underlying facts change only when somebody
// deploys or edits the tool list — a background poll would add traffic against
// the Letta server for no fresher an answer. The Refresh button covers the
// case where they just ran the fix and want to confirm it took.

import { renderMazdaToolReconciliation } from "../abstract/mazda-tool-reconciliation.js";

export function createStatusHome({ doc = document, http }) {
  const body = doc.getElementById("status-home-body");

  return {
    async open() {
      if (!body) return;
      body.innerHTML =
        '<p class="am-dim">Checking Mazda tool registration…</p>';
      try {
        const d = await http.getJSON("/api/mazda-tool-reconciliation");
        body.innerHTML = renderMazdaToolReconciliation(d);
      } catch (e) {
        // A failed fetch is itself a status worth showing. Reuse the
        // unreachable branch rather than blanking the panel.
        //
        // Distinguish *which* thing failed. A 404 means this dashboard has no
        // such route -- it is running a build from before the endpoint
        // existed, and the fix is restarting the service, not touching Letta.
        // Reporting that as "the Letta server hasn't answered" sends whoever
        // reads it to the wrong host; it cost exactly that once already.
        const msg = String(e?.message || e);
        body.innerHTML = renderMazdaToolReconciliation({
          reachable: false,
          text: `Reconciliation check failed: ${msg}`,
          hint: /\b404\b/.test(msg)
            ? "This dashboard has no /api/mazda-tool-reconciliation route, which means it is serving a build from before the check existed. Restart dashboard-server.service."
            : "Cannot tell whether Mazda's tools are in sync until the Letta server answers.",
        });
      }
    },
    bind() {
      doc
        .getElementById("status-home-refresh")
        ?.addEventListener("click", () => this.open());
    },
  };
}
