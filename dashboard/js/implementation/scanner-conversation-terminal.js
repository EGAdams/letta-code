import { isTerminalSession } from "../abstract/terminal-launcher.interface.js";

/**
 * Owns the one live Letta Code terminal used by both Last Scan pages.
 *
 * xterm stays display-only; the textarea sends one complete line through the
 * small TerminalSession port. This avoids per-keystroke browser/pty redraw
 * jitter while preserving the real interactive Letta Code process.
 */
export class ScannerConversationTerminal {
  constructor({ launcher, doc = globalThis.document }) {
    if (!launcher || typeof launcher.open !== "function") {
      throw new TypeError(
        "ScannerConversationTerminal requires a TerminalLauncher",
      );
    }
    this._launcher = launcher;
    this._doc = doc;
    this._session = null;
    this._conversationId = null;
    this._container = null;
    this._generation = 0;
  }

  dispose() {
    this._generation += 1;
    if (this._session) {
      try {
        this._session.dispose();
      } catch {
        /* already disposed */
      }
    }
    if (this._container) {
      this._container.innerHTML = "";
      this._container.classList.add("hidden");
    }
    this._session = null;
    this._conversationId = null;
    this._container = null;
  }

  mount(container, conversationId) {
    if (!container) return null;
    if (!conversationId) {
      this.dispose();
      container.classList.remove("hidden");
      container.textContent =
        "Mazda's scan conversation is unavailable; no fallback session was opened.";
      return null;
    }
    if (this._conversationId === conversationId && this._session) {
      return this._api;
    }

    this.dispose();
    this._conversationId = conversationId;
    this._container = container;
    container.innerHTML = "";
    container.classList.remove("hidden");

    const heading = this._element("h2", "Mazda's Letta Code Terminal");
    const context = this._element(
      "p",
      `Attached to this scan's conversation: ${conversationId}`,
      "mazda-terminal-context",
    );
    const status = this._element(
      "div",
      "Opening the completed scan conversation…",
      "mazda-terminal-status",
    );
    const host = this._element("div", "", "terminal-host");
    const input = this._element("textarea", "", "mazda-terminal-input");
    input.placeholder = "Ask Mazda what happened during this scan…";
    const controls = this._element("div", "", "mazda-terminal-controls");
    const send = this._element("button", "Send to Mazda", "am-btn");
    const restart = this._element("button", "Restart Terminal", "am-btn");
    send.disabled = true;
    controls.append(send, restart);
    container.append(heading, context, status, host, input, controls);

    const showStatus = (message, isError = false) => {
      status.textContent = message;
      status.classList.toggle("error", isError);
    };
    const start = async () => {
      const startGeneration = ++this._generation;
      if (this._session) this._session.dispose();
      this._session = null;
      send.disabled = true;
      restart.disabled = true;
      host.innerHTML = "";
      showStatus("Opening the completed scan conversation…");
      try {
        const session = await this._launcher.open({
          hostEl: host,
          conversationId,
          doc: this._doc,
          onStatus: showStatus,
        });
        if (startGeneration !== this._generation) {
          session?.dispose?.();
          return;
        }
        if (!isTerminalSession(session)) {
          throw new TypeError("terminal launcher returned an invalid session");
        }
        this._session = session;
        send.disabled = false;
      } catch (error) {
        showStatus(error?.message || "Failed to start terminal.", true);
      } finally {
        if (startGeneration === this._generation) restart.disabled = false;
      }
    };
    const sendMessage = () => {
      // The terminal port submits one CLI line. Collapse pasted paragraphs so
      // a single diagnostic question cannot accidentally become several TUI
      // submissions.
      const message = input.value.trim().replace(/\s*\n+\s*/g, " ");
      if (!message || !this._session) return;
      this._session.sendLine(message);
      input.value = "";
      showStatus("Message sent to this scan conversation.");
    };
    send.addEventListener("click", sendMessage);
    restart.addEventListener("click", start);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault?.();
        sendMessage();
      }
    });

    this._api = { start, send: sendMessage, dispose: () => this.dispose() };
    void start();
    return this._api;
  }

  _element(tag, text, className = "") {
    const element = this._doc.createElement(tag);
    element.textContent = text;
    element.className = className;
    return element;
  }
}
