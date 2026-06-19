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

/**
 * Render an array of {type,text} replies to MSI console HTML.
 * When agentName is given, "assistant" rows are labeled with it instead of
 * the literal "assistant" so the user can see which agent replied.
 */
export function renderReplyRows(replies, agentName) {
  if (!replies || !replies.length) {
    return '<div class="msi-entry dim">(no reply content)</div>';
  }
  return replies
    .map((x) => {
      const typeLabel = (x.type || "").replace("_message", "");
      const label =
        typeLabel === "assistant" && agentName ? agentName : typeLabel;
      return `<div class="msi-entry"><span class="hdr">${TextUtils.esc(
        label,
      )}:</span> ${TextUtils.esc(x.text)}</div>`;
    })
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
 * AgentCardRenderer — Strategy for the Agent Card tab.
 *
 * render(target, agentId): GET /api/agent-card?agent=<id> and render the
 * agent's identity / system message / role / responsibilities / tools /
 * memory summary. Reproduces AM.renderAgentCard's markup exactly.
 */
export class AgentCardRenderer extends DetailRenderer {
  constructor({ http, doc = globalThis.document }) {
    super();
    if (!http) throw new Error("AgentCardRenderer requires an HttpClient");
    this._http = http;
    this._doc = doc;
  }

  /** @override */
  async render(target, agentId) {
    const c = this._doc.getElementById(target);
    if (!c) return;
    c.innerHTML =
      '<div class="msi-console"><span class="msi-inner">loading agent card…</span><span class="msi-cursor">&#9608;</span></div>';
    try {
      const card = await this._http.getJSON(
        `/api/agent-card?agent=${encodeURIComponent(agentId)}`,
      );
      const responsibilities = (card.responsibilities || [])
        .map((x) => `<li>${TextUtils.esc(x)}</li>`)
        .join("");
      const tools = (card.tools || [])
        .map((x) => `<li>${TextUtils.esc(x)}</li>`)
        .join("");
      const systemMessage = card.system_message
        ? `<p><strong>System Message:</strong></p><pre class="agent-system-message">${TextUtils.esc(card.system_message)}</pre>`
        : "";
      c.innerHTML =
        '<div class="am-test-out" style="display:block;max-width:980px">' +
        `<h3 style="margin-top:0">${TextUtils.esc(card.identity || card.name || "Agent Card")}</h3>` +
        `<p><strong>Agent ID:</strong> ${TextUtils.esc(card.agent_id || "")}</p>` +
        systemMessage +
        `<p><strong>Role:</strong> ${TextUtils.esc(card.role || "")}</p>` +
        `<p><strong>Core Responsibilities:</strong></p><ul>${responsibilities}</ul>` +
        `<p><strong>Key Tools / Capabilities:</strong></p><ul>${tools}</ul>` +
        `<p><strong>Self-Improvement / Memory Summary:</strong><br>${TextUtils.esc(card.memory_summary || "")}</p>` +
        "</div>";
    } catch (e) {
      c.innerHTML = `<div class="msi-console"><span class="msi-line err">! ${TextUtils.esc(e.message)}</span></div>`;
    }
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
    onStatus = () => {},
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
    this._onStatus = onStatus;
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

    const consoleWrap = this._el("div");
    container.append(heading, consoleWrap);
    const out = DomConsoleView.mount(consoleWrap, "am-chat", this._doc);
    // Match the live console styling/id (msi-console am-test-out #am-chat-out).
    const box = consoleWrap.querySelector(".msi-console");
    if (box) {
      box.classList.add("am-test-out");
      box.id = "am-chat-out";
    }
    out.replaceHtml(
      '<div class="msi-entry dim">&mdash; chat replies will appear here &mdash;</div>',
    );

    const textEl = this._el("textarea", {
      className: "am-test-input",
      placeholder: "Type a message, or press Start to speak...",
    });
    const controls = this._el("div", { className: "am-controls" });
    const sendBtn = this._el("button", {
      className: "am-btn",
      textContent: "Send",
    });
    const voiceBtn = this._el("button", {
      className: "am-btn voice-btn",
      textContent: "Start",
    });
    // Recording indicator (animated "Recording..." while capturing).
    const recInd = this._el("span", { className: "rec-indicator" });
    const recLed = this._el("span", { className: "rec-led" });
    const recText = this._el("span", {
      className: "rec-text",
      textContent: "Recording",
    });
    recInd.append(recLed, recText);
    const modeBtn = this._el("button", {
      className: "am-btn am-mode",
      textContent: "Auto Send",
      title: "Toggle what happens after voice cleanup",
    });
    modeBtn.dataset.mode = "auto";
    const speakBtn = this._el("button", {
      className: "am-btn am-speak",
      title: "Read agent replies aloud (browser text-to-speech)",
    });
    const copyBtn = this._el("button", {
      className: "am-btn am-copy",
      textContent: "Copy to Clipboard",
      title: "Copy selected text to the clipboard",
    });
    controls.append(sendBtn, voiceBtn, recInd, modeBtn, speakBtn, copyBtn);
    container.append(textEl, controls);

    const setConsole = (html) => {
      out.replaceHtml(html);
      out.scrollToBottom();
    };

    // ── Speak-replies toggle (preference persists) ─────────────────────────
    let speakReplies =
      this._storage && this._storage.getItem("dash-speak-replies") === "1";
    const renderSpeakBtn = () => {
      if (!this._speech || !this._speech.supported) {
        speakBtn.disabled = true;
        speakBtn.textContent = "🔇 Speak";
        speakBtn.title = "This browser has no SpeechSynthesis support";
        return;
      }
      speakBtn.classList.toggle("on", speakReplies);
      speakBtn.textContent = speakReplies ? "🔊 Speak" : "🔈 Speak";
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
      this._onStatus(id, "active");
      try {
        const r = await this._http.postJSON(this._endpoint, {
          agent: id,
          text,
        });
        const replies = r.replies || [];
        const hasError = replies.some((x) => x.type === "error");
        this._onStatus(id, hasError ? "error" : "idle");
        setConsole(renderReplyRows(replies));
        // Read the agent's reply aloud in the agent's own voice.
        if (speakReplies && this._speech && replies.length) {
          this._speech.speak(composeSpokenText(replies), this._agentName);
        }
      } catch (e) {
        this._onStatus(id, "error");
        setConsole(
          `<div class="msi-line err">! ${TextUtils.esc(e.message)}</div>`,
        );
      }
    };
    sendBtn.addEventListener("click", () => sendText(textEl.value));

    // Auto Send <-> Review then Send. Copy only makes sense while reviewing.
    const renderCopyVisibility = () => {
      copyBtn.style.display = modeBtn.dataset.mode === "auto" ? "none" : "";
    };
    modeBtn.addEventListener("click", () => {
      const auto = modeBtn.dataset.mode === "auto";
      modeBtn.dataset.mode = auto ? "review" : "auto";
      modeBtn.textContent = auto ? "Review then Send" : "Auto Send";
      renderCopyVisibility();
    });
    renderCopyVisibility();

    // ── Voice capture (delegates the state machine to VoiceRecorder) ───────
    let dots = 0;
    let recTimer = null;
    const cycleRecText = () => {
      recText.textContent = `Recording${".".repeat(dots)}`;
      dots = (dots + 1) % 4;
    };
    const recorder = this._recorderFactory({
      onStateChange: (state) => {
        const recording = state === RecorderState.RECORDING;
        voiceBtn.classList.toggle("recording", recording);
        voiceBtn.textContent = recording ? "Stop" : "Start";
        voiceBtn.disabled = state === RecorderState.PROCESSING;
        recInd.classList.toggle("on", recording);
        if (recording) {
          dots = 0;
          cycleRecText();
          recTimer = setInterval(cycleRecText, 450);
        } else if (recTimer) {
          clearInterval(recTimer);
          recTimer = null;
        }
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
            '<div class="msi-line err">! Microphone needs a secure context (https). Open this dashboard via the Tailscale https URL.</div>',
          );
        }
      }
    });

    // ── Copy to Clipboard: copies whatever text is currently selected ──────
    copyBtn.addEventListener("click", () => {
      const win = this._doc.defaultView || globalThis;
      const nav = win.navigator;
      let selected = "";
      const active = this._doc.activeElement;
      if (
        active &&
        (active.tagName === "TEXTAREA" || active.tagName === "INPUT") &&
        typeof active.selectionStart === "number" &&
        active.selectionStart !== active.selectionEnd
      ) {
        selected = active.value.substring(
          active.selectionStart,
          active.selectionEnd,
        );
      } else {
        selected = (win.getSelection() || "").toString();
      }
      if (!selected) {
        setConsole('<div class="msi-line err">! No text selected.</div>');
        return;
      }
      const onCopied = () =>
        setConsole(
          '<div class="msi-entry">Copied selected text to clipboard.</div>',
        );
      const onFailed = () =>
        setConsole(
          '<div class="msi-line err">! Clipboard access was blocked by the browser.</div>',
        );
      const legacyCopy = (text) => {
        const ta = this._doc.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        this._doc.body.appendChild(ta);
        ta.focus();
        ta.select();
        let ok = false;
        try {
          ok = this._doc.execCommand("copy");
        } catch {
          ok = false;
        }
        this._doc.body.removeChild(ta);
        return ok;
      };
      if (nav && nav.clipboard && nav.clipboard.writeText) {
        nav.clipboard.writeText(selected).then(onCopied, () => {
          if (legacyCopy(selected)) onCopied();
          else onFailed();
        });
      } else if (legacyCopy(selected)) {
        onCopied();
      } else {
        onFailed();
      }
    });

    return { sendText, recorder };
  }
}

/**
 * InputOptionsRenderer — Strategy for the "Input Options" tab.
 *
 * Same voice/http/speech pipeline as the chat tab but a different, vertically
 * stacked layout (textarea + Send + Start/Stop + Auto Send + Speak + Copy +
 * status line). Reproduces AM.renderInputOptions: Auto Send / Speak are sticky
 * toggles, voice fills the textarea and (when Auto Send is on) clicks Send.
 */
export class InputOptionsRenderer extends DetailRenderer {
  constructor({
    http,
    speech,
    agentName = "the agent",
    agentId = null,
    onStatus = () => {},
    doc = globalThis.document,
    recorderFactory = (opts) => new MediaRecorderVoiceRecorder(opts),
    endpoint = "/api/test",
  }) {
    super();
    if (!http) throw new Error("InputOptionsRenderer requires an HttpClient");
    this._http = http;
    this._speech = speech;
    this._agentName = agentName;
    this._agentId = agentId;
    this._onStatus = onStatus;
    this._doc = doc;
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

    // Buttons sized like tabs but ~35% taller, left-aligned, full width.
    const bs =
      "width:100%;padding:11px 8px;font-size:0.9rem;line-height:1.15;border-radius:4px;border:0;cursor:pointer;color:#fff;text-align:left;";

    const heading = this._el("p");
    heading.innerHTML = `Input options for <strong>${TextUtils.esc(this._agentName)}</strong>:`;

    const col = this._el("div");
    col.style.cssText =
      "display:flex;flex-direction:column;gap:10px;max-width:320px;";

    const textEl = this._el("textarea", {
      className: "am-test-input",
      placeholder: "Type or speak here…",
    });
    textEl.style.cssText = "min-height:100px;";

    const sendBtn = this._el("button", { textContent: "Send" });
    sendBtn.style.cssText = `${bs}background:#4c6ef5;`;

    const voiceRow = this._el("div");
    voiceRow.style.cssText = "display:flex;align-items:center;gap:8px;";
    const startBtn = this._el("button", {
      className: "voice-btn",
      textContent: "Start",
    });
    startBtn.style.cssText = `${bs}flex:1;background:#28a745;`;
    const recInd = this._el("span", { className: "rec-indicator" });
    const recLed = this._el("span", { className: "rec-led" });
    const recText = this._el("span", {
      className: "rec-text",
      textContent: "Recording",
    });
    recInd.append(recLed, recText);
    voiceRow.append(startBtn, recInd);

    const autoSendBtn = this._el("button", { textContent: "Auto Send" });
    autoSendBtn.style.cssText = `${bs}background:#6c757d;`;
    const speakBtn = this._el("button");
    speakBtn.innerHTML = "&#128266; Speak";
    speakBtn.style.cssText = `${bs}background:#6c757d;`;
    const copyBtn = this._el("button", { textContent: "Copy to Clipboard" });
    copyBtn.style.cssText = `${bs}background:#6c757d;`;
    const statusEl = this._el("div");
    statusEl.style.cssText = "min-height:1.4em;font-size:0.9rem;color:#555;";
    const outEl = this._el("div", { className: "am-test-out" });

    col.append(
      textEl,
      sendBtn,
      voiceRow,
      autoSendBtn,
      speakBtn,
      copyBtn,
      statusEl,
      outEl,
    );
    container.append(heading, col);

    let autoSendOn = false;
    let speakOn = false;

    const showStatus = (msg, isError) => {
      statusEl.style.color = isError ? "#c0392b" : "#555";
      statusEl.textContent = msg;
    };

    autoSendBtn.addEventListener("click", () => {
      autoSendOn = !autoSendOn;
      autoSendBtn.style.background = autoSendOn ? "#2f55e7" : "#6c757d";
      autoSendBtn.style.fontWeight = autoSendOn ? "700" : "";
    });
    speakBtn.addEventListener("click", () => {
      speakOn = !speakOn;
      speakBtn.style.background = speakOn ? "#2f55e7" : "#6c757d";
      speakBtn.style.fontWeight = speakOn ? "700" : "";
    });

    // ── Copy to Clipboard ──────────────────────────────────────────────────
    copyBtn.addEventListener("click", () => {
      const win = this._doc.defaultView || globalThis;
      const nav = win.navigator;
      let selected = "";
      const active = this._doc.activeElement;
      if (
        active &&
        (active.tagName === "TEXTAREA" || active.tagName === "INPUT") &&
        active.selectionStart !== active.selectionEnd
      ) {
        selected = active.value.substring(
          active.selectionStart,
          active.selectionEnd,
        );
      } else {
        const sel = win.getSelection();
        if (sel) selected = sel.toString();
      }
      if (!selected) {
        showStatus("No text selected.", true);
        return;
      }
      const ok = () => showStatus("Copied selected text to clipboard.");
      const fail = () =>
        showStatus("Clipboard access blocked by browser.", true);
      const legacyCopy = () => {
        try {
          const ta = this._doc.createElement("textarea");
          ta.value = selected;
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          this._doc.body.appendChild(ta);
          ta.focus();
          ta.select();
          this._doc.execCommand("copy");
          this._doc.body.removeChild(ta);
          return true;
        } catch {
          return false;
        }
      };
      if (nav && nav.clipboard && nav.clipboard.writeText) {
        nav.clipboard.writeText(selected).then(ok, () => {
          if (legacyCopy()) ok();
          else fail();
        });
      } else if (legacyCopy()) {
        ok();
      } else {
        fail();
      }
    });

    // ── Send to the agent through /api/test ────────────────────────────────
    const send = async () => {
      const text = textEl.value;
      if (!text.trim()) {
        showStatus("Nothing to send.", true);
        return;
      }
      textEl.value = "";
      const userRow = `<div class="msi-entry"><span class="hdr">user:</span> ${TextUtils.esc(text)}</div>`;
      outEl.innerHTML = `<div class="msi-console">${userRow}<div class="msi-gap"></div><span class="msi-cursor">&#9608;</span> sending&hellip;</div>`;
      showStatus("");
      this._onStatus(id, "active");
      try {
        const r = await this._http.postJSON(this._endpoint, {
          agent: id,
          text,
        });
        const replies = r.replies || [];
        const hasError = replies.some((x) => x.type === "error");
        this._onStatus(id, hasError ? "error" : "idle");
        outEl.innerHTML = `<div class="msi-console">${userRow}<div class="msi-gap"></div>${renderReplyRows(replies, this._agentName)}</div>`;
        if (speakOn && this._speech) {
          const replyText = replies.map((x) => x.text || "").join(" ");
          if (replyText) this._speech.speak(replyText, this._agentName);
        }
      } catch (e) {
        this._onStatus(id, "error");
        outEl.innerHTML = `<div class="msi-console">${userRow}<div class="msi-gap"></div><span class="msi-line err">! ${TextUtils.esc(e.message)}</span></div>`;
      }
    };
    sendBtn.addEventListener("click", send);

    // ── Voice capture (delegates the state machine to VoiceRecorder) ───────
    let dots = 0;
    let recTimer = null;
    const cycleRecText = () => {
      recText.textContent = `Recording${".".repeat(dots)}`;
      dots = (dots + 1) % 4;
    };
    const recorder = this._recorderFactory({
      onStateChange: (state) => {
        const recording = state === RecorderState.RECORDING;
        startBtn.classList.toggle("recording", recording);
        startBtn.textContent = recording ? "Stop" : "Start";
        startBtn.disabled = state === RecorderState.PROCESSING;
        recInd.classList.toggle("on", recording);
        if (recording) {
          dots = 0;
          cycleRecText();
          recTimer = setInterval(cycleRecText, 450);
        } else if (recTimer) {
          clearInterval(recTimer);
          recTimer = null;
        }
      },
    });
    startBtn.addEventListener("click", async () => {
      if (recorder.isRecording) {
        showStatus("Transcribing & cleaning up…");
        let data;
        try {
          data = await recorder.stop();
        } catch (e) {
          showStatus(e.message, true);
          return;
        }
        if (!data) return;
        textEl.value = data.cleaned_text || "";
        showStatus("Transcribed & cleaned. Tap Send or enable Auto Send.");
        if (autoSendOn) await send();
      } else {
        showStatus("Listening…");
        const ok = await recorder.start();
        if (!ok) {
          showStatus(
            "Microphone needs a secure context (https). Open this dashboard via the Tailscale https URL.",
            true,
          );
        }
      }
    });

    return { send, recorder };
  }
}
