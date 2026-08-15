import { ListenerState } from "../abstract/continuous-listener.interface.js";
import { VoiceCommandChannel } from "../abstract/voice-command-channel.js";

const BUTTON =
  "width:100%;padding:11px 8px;font-size:0.9rem;line-height:1.15;border-radius:4px;border:0;cursor:pointer;color:#fff;text-align:left;";

/**
 * NoteCommandPanelRenderer — the DOM for the command box, and nothing else.
 *
 * It renders the second text area, wires a ContinuousListener into a
 * VoiceCommandChannel, and paints that channel's status. Every decision about
 * *when* a spoken instruction is finished and *what* it does to the note lives
 * in the channel (see voice-command-channel.js), which has no DOM in it.
 *
 * This is a separate renderer from the note box above it on purpose: the note
 * box is an agent-messaging widget that Toyota happens to reuse, and folding a
 * command channel into it would have meant another mode flag inside an already
 * long renderer.
 */
export class NoteCommandPanelRenderer {
  constructor({
    note,
    listener,
    completenessDetector,
    commandInterpreter,
    doc = globalThis.document,
    channelFactory = (options) => new VoiceCommandChannel(options),
  }) {
    if (!note)
      throw new Error("NoteCommandPanelRenderer requires a NoteDocument");
    if (!listener)
      throw new Error("NoteCommandPanelRenderer requires a ContinuousListener");
    this._note = note;
    this._listener = listener;
    this._completenessDetector = completenessDetector;
    this._commandInterpreter = commandInterpreter;
    this._doc = doc;
    this._channelFactory = channelFactory;
  }

  _el(tag, props = {}) {
    const el = this._doc.createElement(tag);
    Object.assign(el, props);
    return el;
  }

  render(target) {
    const container = this._doc.getElementById(target);
    if (!container) return null;
    container.innerHTML = "";

    const col = this._el("div");
    col.style.cssText =
      "display:flex;flex-direction:column;gap:10px;max-width:320px;margin-top:14px;";

    const label = this._el("p", {
      textContent: "Tell Toyota how to change the note:",
    });
    label.style.cssText = "margin:0;font-size:0.9rem;color:#555;";

    const commandEl = this._el("textarea", {
      className: "note-command-input",
      placeholder: 'e.g. "Put a period at the end" — or "Save this"',
    });
    commandEl.style.cssText = "min-height:70px;";

    const listenBtn = this._el("button", {
      className: "voice-btn note-command-listen",
      textContent: "Start Command Listening",
    });
    listenBtn.style.cssText = `${BUTTON}background:#17a2b8;`;

    const runBtn = this._el("button", {
      className: "note-command-run",
      textContent: "Run Command",
    });
    runBtn.style.cssText = `${BUTTON}background:#4c6ef5;`;

    const clearBtn = this._el("button", {
      className: "note-command-clear",
      textContent: "Clear Command",
    });
    clearBtn.style.cssText = `${BUTTON}background:#6c757d;`;

    const statusEl = this._el("div", { className: "note-command-status" });
    statusEl.style.cssText = "min-height:1.4em;font-size:0.9rem;color:#555;";

    col.append(label, commandEl, listenBtn, runBtn, clearBtn, statusEl);
    container.append(col);

    const showStatus = (message, isError) => {
      statusEl.style.color = isError ? "#c0392b" : "#555";
      statusEl.textContent = message;
    };

    const channel = this._channelFactory({
      note: this._note,
      completenessDetector: this._completenessDetector,
      commandInterpreter: this._commandInterpreter,
      // The command box shows the accumulated instruction, including the
      // interim words, so a pause mid-sentence is visible rather than silent.
      onCommandText: ({ text }) => {
        commandEl.value = text;
      },
      onStatus: showStatus,
    });

    const syncListenBtn = (state) => {
      const listening = state === ListenerState.LISTENING;
      listenBtn.classList.toggle("recording", listening);
      listenBtn.textContent = listening
        ? "Stop Command Listening"
        : "Start Command Listening";
    };

    this._listener.setCallbacks({
      onStateChange: syncListenBtn,
      onResult: (text, isFinal) => channel.handleSpeech(text, isFinal),
      onError: (message) => showStatus(message, true),
    });
    syncListenBtn(this._listener.state);

    listenBtn.addEventListener("click", async () => {
      if (this._listener.isListening) {
        this._listener.stop();
        return;
      }
      showStatus("Listening for commands…");
      const ok = await this._listener.start();
      if (!ok) {
        showStatus("Speech recognition isn't available in this browser.", true);
      }
    });

    // Typed commands take the identical path — the channel is told the
    // instruction is finished instead of asking the detector.
    runBtn.addEventListener("click", () => channel.submit(commandEl.value));
    clearBtn.addEventListener("click", () => {
      channel.clear();
      showStatus("");
    });

    return { channel, commandTextarea: commandEl, listener: this._listener };
  }
}
