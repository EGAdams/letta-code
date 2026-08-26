// scanner-agent-views.js — the two agent-driven panels the scanner report tabs
// mount: Mazda's live Thoughts, and the archive-verification terminal.
//
// They live outside the agent-detail fanout (a scanner report tab is not an
// agent tab), but they drive the same AgentStreamController / mountTerminal
// collaborators, so they are grouped here rather than in agent-manager.js.

import {
  buildArchiveVerifyCommand,
  readArchivePathResponse,
} from "../abstract/archive-verify-command.js";
import { TextUtils } from "../abstract/text-utils.js";
import {
  AgentStreamController,
  DomConsoleView,
  mountTerminal,
} from "../implementation/index.js";

const esc = TextUtils.esc;
const MAZDA_AGENT_ID = "agent-6b536cf4-ec88-4290-b595-fed21d14bd8e";

export function createScannerAgentViews({ doc = document, http }) {
  // xterm.js's DOM renderer only reliably paints one live Terminal instance
  // per page — a second concurrent instance (e.g. switching from "Last Window
  // Scan" to "Last Freezer Scan") writes to its internal buffer correctly but
  // never repaints the DOM, even under an explicit term.refresh(). Keep at
  // most one archive-verification terminal mounted at a time.
  let archiveTerminalSession = null;

  // Render Mazda's Thoughts into a specific DOM container (for scanner report
  // tabs).
  function renderMazdaThoughtsInto(container, scannerKey = "") {
    if (!container) return;
    container.innerHTML = "";
    const heading = doc.createElement("h2");
    heading.textContent = "Mazda's Thoughts";
    heading.style.cssText = "margin-top:20px;margin-bottom:10px;";
    container.appendChild(heading);
    // DomConsoleView.mount() clears its container via innerHTML — mount it
    // into a dedicated child so it doesn't wipe out the heading above.
    const consoleHost = doc.createElement("div");
    container.appendChild(consoleHost);
    const consoleView = DomConsoleView.mount(
      consoleHost,
      "mazda-thoughts-console",
      doc,
    );
    const controller = new AgentStreamController({
      http,
      view: consoleView,
      url: scannerKey
        ? `/api/thoughts?scanner=${encodeURIComponent(scannerKey)}`
        : "/api/thoughts",
      agentId: MAZDA_AGENT_ID,
      label: "thoughts",
      intervalMs: 3000,
    });
    // Don't use the shared poller; run independently with error handling.
    const poll = async () => {
      try {
        await controller.poll();
      } catch (e) {
        consoleView.replaceHtml(
          `<div class="msi-line err">! Failed to load thoughts: ${esc(e.message)}</div>`,
        );
      }
    };
    setInterval(poll, controller.intervalMs || 3000);
    poll(); // Initial poll
  }

  // Show archive verification terminal for a completed scanner report.
  function showArchiveTerminalForScanner(
    scannerKey,
    containerSelector,
    expenseId = null,
  ) {
    const container = doc.querySelector(containerSelector);
    if (!container) return;

    // Dispose any previously-mounted archive terminal AND remove its DOM
    // element (see archiveTerminalSession comment) — disposing the xterm
    // session alone leaves the old .terminal-host element in the document,
    // which is enough to stop a newly-mounted instance's DOM renderer from
    // ever painting, even though it keeps writing into its own buffer fine.
    if (archiveTerminalSession) {
      try {
        archiveTerminalSession.session.dispose();
      } catch {
        /* already disposed */
      }
      archiveTerminalSession.hostEl.remove();
      archiveTerminalSession = null;
    }
    // Clear this container too, in case the same tab is revisited.
    container.innerHTML = "";

    http
      .postJSON("/api/scanner-archive-path", {
        scanner: scannerKey,
        ...(expenseId ? { expense_id: expenseId } : {}),
      })
      .then((json) => {
        const result = readArchivePathResponse(json);
        if (!result.ok) {
          container.classList.remove("hidden");
          container.innerHTML = `<div class="msi-line err">! Archive verification unavailable: ${esc(result.error)}</div>`;
          return;
        }
        container.classList.remove("hidden");
        const heading = doc.createElement("h3");
        heading.textContent = `Archive Verification (${result.archivePath})`;
        container.appendChild(heading);
        const hostEl = doc.createElement("div");
        hostEl.className = "terminal-host";
        container.appendChild(hostEl);

        mountTerminal({ hostEl, doc, onStatus: () => {} }).then((session) => {
          archiveTerminalSession = { session, hostEl };
          if (session?.sendLine) {
            // -a1 forces one entry per line instead of ls's default
            // multi-column layout, which was wrapping across several rows.
            // ANSI 102 is a light-green background; the exact durable archive
            // file returned by the server is highlighted in the listing.
            session.sendLine(
              buildArchiveVerifyCommand(result.archivePath, result.archiveName),
            );
          }
        });
      })
      .catch((e) => {
        container.classList.remove("hidden");
        container.innerHTML = `<div class="msi-line err">! Error: ${esc(e.message)}</div>`;
      });
  }

  return { renderMazdaThoughtsInto, showArchiveTerminalForScanner };
}
