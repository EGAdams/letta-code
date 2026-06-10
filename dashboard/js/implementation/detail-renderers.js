import { DetailRenderer } from "../abstract/detail-renderer.interface.js";
import { TextUtils } from "../abstract/text-utils.js";
import { RecorderState } from "../abstract/voice-recorder.interface.js";
import { AgentStreamController } from "./agent-stream-controller.js";
import { DomConsoleView } from "./dom-console-view.js";
import { MediaRecorderVoiceRecorder } from "./media-recorder-voice-recorder.js";

/**
 * Pure helpers extracted from AM.renderChatInterface so they can be tested
 * without a DOM. ───────────────────────────────────────────────────────────
 */

/** Pick the text to read aloud: prefer assistant/send_message replies. */
export function composeSpokenText(replies) {
  if (!replies || !replies.length) return "";
  const preferred = replies
    .filter((x) => /assistant|send_message/i.test(x.type || "") || !x.type)
    .map((x) => x.text)
    .join(". ");
  return preferred || replies.map((x) => x.text).join(". ");
}

/** Render an array of {type,text} replies to MSI console HTML. */
export function renderReplyRows(replies) {
  if (!replies || !replies.length) {
    return '<div class="msi-entry dim">(no reply content)</div>';
  }
  return replies
    .map(
      (x) =>
        `<div class="msi-entry"><span class="hdr">${TextUtils.esc(
          (x.type || "").replace("_message", ""),
        )}</span> ${TextUtils.esc(x.text)}</div>`,
    )
    .join("");
}

/**
 * StreamDetailRenderer — Strategy for the thoughts / messages / tool-calls tabs.
 *
 * render(target, agentId): mount an MSI console into the section element, build
 * an AgentStreamController bound to this strategy's url+label, and hand it to the
 * shared ActivePoller (which stops any previously-running stream first).
 */
export class StreamDetailRenderer extends DetailRenderer {
  constructor({
    http,
    url,
    label,
    poller,
    doc = globalThis.document,
    intervalMs = 3000,
    // injection seams for tests:
    viewFactory = (container, id) => DomConsoleView.mount(container, id, doc),
    controllerFactory = (opts) => new AgentStreamController(opts),
  }) {
    super();
    if (!http || !url || !poller) {
      throw new Error("StreamDetailRenderer requires { http, url, poller }");
    }
    this._http = http;
    this._url = url;
    this._label = label || "entries";
    this._poller = poller;
    this._doc = doc;
    this._intervalMs = intervalMs;
    this._viewFactory = viewFactory;
    this._controllerFactory = controllerFactory;
  }

  /** @override */
  render(target, agentId) {
    const container = this._doc.getElementById(target);
    if (!container) return;
    const view = this._viewFactory(container, target);
    const controller = this._controllerFactory({
      http: this._http,
      view,
      url: this._url,
      agentId,
      label: this._label,
      intervalMs: this._intervalMs,
    });
    this._poller.run(controller);
    return controller;
  }
}

/**
 * ChatDetailRenderer — Strategy for the chat-interface tab.
 *
 * render(target, agentId): build the chat UI inside the section, then wire:
 *   • Send / textarea           → POST /api/test via the HttpClient
 *   • mic button                → MediaRecorderVoiceRecorder (state → button)
 *   • Speak-replies toggle      → SpeechSynthesizer (+ localStorage preference)
 *   • Auto / Review mode toggle → whether cleaned transcript auto-sends
 *
 * The DOM is assembled with createElement (not an innerHTML string) so the
 * wiring stays queryable and the renderer is unit-testable with a DOM double.
 */
export class ChatDetailRenderer extends DetailRenderer {
  constructor({
    http,
    speech,
    agentName = "the agent",
    agentId = null,
    doc = globalThis.document,
    storage = globalThis.localStorage,
    recorderFactory = (opts) => new MediaRecorderVoiceRecorder(opts),
    endpoint = "/api/test",
  }) {
    super();
    if (!http) throw new Error("ChatDetailRenderer requires an HttpClient");
    this._http = http;
    this._speech = speech;
    this._agentName = agentName;
    this._agentId = agentId;
    this._doc = doc;
    this._storage = storage;
    this._recorderFactory = recorderFactory;
    this._endpoint = endpoint;
  }

  _el(tag, props = {}) {
    const el = this._doc.createElement(tag);
    Object.assign(el, props);
    return el;
  }

  /** @override */
  render(target, agentId) {
    const id = agentId || this._agentId;
    const container = this._doc.getElementById(target);
    if (!container) return null;
    container.innerHTML = "";

    const heading = this._el("p");
    heading.innerHTML = `Meeting with <strong>${TextUtils.esc(this._agentName)}</strong>:`;

    const out = DomConsoleView.mount(
      container.appendChild(this._el("div")),
      "am-chat",
      this._doc,
    );
    out.renderEmptyOnce(
      '<div class="msi-entry dim">&mdash; chat replies will appear here &mdash;</div>',
    );

    const textEl = this._el("textarea", {
      className: "am-test-input",
      placeholder: "Type a message, or press Start to speak...",
    });
    const sendBtn = this._el("button", {
      className: "am-btn",
      textContent: "Send",
    });
    const voiceBtn = this._el("button", {
      className: "am-btn voice-btn",
      textContent: "Start",
    });
    const modeBtn = this._el("button", {
      className: "am-btn am-mode",
      textContent: "Auto Send",
    });
    modeBtn.dataset.mode = "auto";
    const speakBtn = this._el("button", { className: "am-btn am-speak" });

    container.prepend(heading);
    container.append(textEl, sendBtn, voiceBtn, modeBtn, speakBtn);

    const setConsole = (html) => out.replaceHtml(html);

    // ── Speak-replies toggle (preference persists) ─────────────────────────
    let speakReplies =
      this._storage && this._storage.getItem("dash-speak-replies") === "1";
    const renderSpeakBtn = () => {
      if (!this._speech || !this._speech.supported) {
        speakBtn.disabled = true;
        speakBtn.textContent = "🔇 TTS N/A";
        return;
      }
      speakBtn.classList.toggle("on", speakReplies);
      speakBtn.textContent = speakReplies
        ? "🔊 Speaking On"
        : "🔈 Speak Replies";
    };
    speakBtn.addEventListener("click", () => {
      speakReplies = !speakReplies;
      if (this._storage)
        this._storage.setItem("dash-speak-replies", speakReplies ? "1" : "0");
      if (!speakReplies && this._speech) this._speech.cancel();
      renderSpeakBtn();
    });
    renderSpeakBtn();

    // ── Send text to the agent through /api/test ───────────────────────────
    const sendText = async (text) => {
      if (!text || !text.trim()) return;
      setConsole('<div class="msi-entry dim">sending&hellip;</div>');
      try {
        const r = await this._http.postJSON(this._endpoint, {
          agent: id,
          text,
        });
        const replies = r.replies || [];
        setConsole(renderReplyRows(replies));
        if (speakReplies && this._speech && replies.length) {
          this._speech.speak(composeSpokenText(replies));
        }
      } catch (e) {
        setConsole(
          `<div class="msi-line err">! ${TextUtils.esc(e.message)}</div>`,
        );
      }
    };
    sendBtn.addEventListener("click", () => sendText(textEl.value));

    // Auto Send <-> Review then Send.
    modeBtn.addEventListener("click", () => {
      const auto = modeBtn.dataset.mode === "auto";
      modeBtn.dataset.mode = auto ? "review" : "auto";
      modeBtn.textContent = auto ? "Review then Send" : "Auto Send";
    });

    // ── Voice capture (delegates the state machine to VoiceRecorder) ───────
    const recorder = this._recorderFactory({
      onStateChange: (state) => {
        voiceBtn.classList.toggle(
          "recording",
          state === RecorderState.RECORDING,
        );
        voiceBtn.textContent =
          state === RecorderState.RECORDING ? "Stop" : "Start";
        voiceBtn.disabled = state === RecorderState.PROCESSING;
      },
    });
    voiceBtn.addEventListener("click", async () => {
      if (recorder.isRecording) {
        setConsole(
          '<div class="msi-entry dim">transcribing &amp; cleaning up&hellip;</div>',
        );
        let data;
        try {
          data = await recorder.stop();
        } catch (e) {
          setConsole(
            `<div class="msi-line err">! ${TextUtils.esc(e.message)}</div>`,
          );
          return;
        }
        if (!data) return;
        const raw = data.raw_transcript || "";
        const cleaned = data.cleaned_text || "";
        textEl.value = cleaned;
        let info = `<div class="msi-entry"><span class="hdr">heard</span> ${TextUtils.esc(raw)}</div>`;
        if (cleaned && cleaned !== raw) {
          info += `<div class="msi-entry"><span class="hdr">cleaned</span> ${TextUtils.esc(cleaned)}</div>`;
        }
        setConsole(info);
        if (modeBtn.dataset.mode === "auto") await sendText(cleaned);
      } else {
        const ok = await recorder.start();
        if (!ok) {
          setConsole(
            '<div class="msi-line err">! Microphone needs a secure context (https) and permission.</div>',
          );
        }
      }
    });

    return { sendText, recorder };
  }
}
