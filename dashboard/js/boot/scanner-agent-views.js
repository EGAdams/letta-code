// scanner-agent-views.js — the two agent-driven panels the scanner report tabs
// mount: Mazda's live Thoughts, its scan-scoped Letta Code terminal, and the
// archive-verification evidence.
//
// They live outside the agent-detail fanout (a scanner report tab is not an
// agent tab), but they drive the same AgentStreamController / TerminalLauncher
// collaborators, so they are grouped here rather than in agent-manager.js.

import { readArchivePathResponse } from "../abstract/archive-verify-command.js";
import { TextUtils } from "../abstract/text-utils.js";
import {
  AgentStreamController,
  DomConsoleView,
} from "../implementation/index.js";
import { ScannerConversationTerminal } from "../implementation/scanner-conversation-terminal.js";

const esc = TextUtils.esc;
const MAZDA_AGENT_ID = "agent-6b536cf4-ec88-4290-b595-fed21d14bd8e";

export function createScannerAgentViews({
  doc = document,
  http,
  terminalLauncher,
}) {
  const thoughtControllers = new Map();
  const conversationTerminal = new ScannerConversationTerminal({
    launcher: terminalLauncher,
    doc,
  });

  // Render Mazda's Thoughts into a specific DOM container (for scanner report
  // tabs).
  function renderMazdaThoughtsInto(container, scannerKey = "") {
    if (!container) return;
    thoughtControllers.get(container)?.stop();
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
    thoughtControllers.set(container, controller);
    void controller.start();
  }

  function showMazdaTerminalForScanner(containerSelector, conversationId) {
    conversationTerminal.mount(
      doc.querySelector(containerSelector),
      conversationId,
    );
  }

  function clearScannerCompletionViews(terminalSelector, archiveSelector) {
    conversationTerminal.dispose();
    for (const selector of [terminalSelector, archiveSelector]) {
      const container = doc.querySelector(selector);
      if (!container) continue;
      container.innerHTML = "";
      container.classList.add("hidden");
    }
  }

  // Show archive evidence without starting a second shell/xterm process.
  function showArchiveVerificationForScanner(
    scannerKey,
    containerSelector,
    expenseId = null,
  ) {
    const container = doc.querySelector(containerSelector);
    if (!container) return;

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
        heading.textContent = "Archive Verification";
        container.appendChild(heading);
        const proof = doc.createElement("p");
        proof.className = "archive-verification-path";
        proof.textContent = `✓ ${result.archivePath}/${result.archiveName}`;
        container.appendChild(proof);
      })
      .catch((e) => {
        container.classList.remove("hidden");
        container.innerHTML = `<div class="msi-line err">! Error: ${esc(e.message)}</div>`;
      });
  }

  return {
    renderMazdaThoughtsInto,
    clearScannerCompletionViews,
    showMazdaTerminalForScanner,
    showArchiveVerificationForScanner,
  };
}
