import { ListenerState } from "../abstract/continuous-listener.interface.js";
import { RecorderState } from "../abstract/voice-recorder.interface.js";
import { buildModelRow } from "./detail-renderers.js";
import { MediaRecorderVoiceRecorder } from "./media-recorder-voice-recorder.js";

/**
 * AgentsRouterRenderer — Strategy for the Agents home page.
 *
 * Replaces the old static "Loaded N agents…" status line with a lightweight
 * router: the user talks or types, and as soon as a known agent's name is
 * detected (via POST /api/route-detect), this hands off to that agent's
 * existing Input Options page — passing only the text *after* the name — and
 * keeps listening without interruption.
 *
 * `listener` is an externally-owned, long-lived ContinuousListener (see
 * dashboard-boot.js): render() re-claims it via setCallbacks() each time this
 * page is (re)opened, so the actual listening session survives navigation
 * even though this renderer itself is rebuilt fresh per the existing
 * per-open-renderer convention (see InputOptionsRenderer).
 *
 * `resolveAgentId`/`openAgent` are injected so this class never touches the
 * global AM facade directly — dashboard-boot.js supplies thin adapters.
 */
export class AgentsRouterRenderer {
  constructor({
    http,
    listener,
    resolveAgentId,
    openAgent,
    onStatus = () => {},
    doc = globalThis.document,
    recorderFactory = (opts) => new MediaRecorderVoiceRecorder(opts),
  }) {
    if (!http) throw new Error("AgentsRouterRenderer requires an HttpClient");
    if (!listener)
      throw new Error("AgentsRouterRenderer requires a ContinuousListener");
    if (!resolveAgentId || !openAgent)
      throw new Error(
        "AgentsRouterRenderer requires resolveAgentId + openAgent",
      );
    this._http = http;
    this._listener = listener;
    this._resolveAgentId = resolveAgentId;
    this._openAgent = openAgent;
    this._onStatus = onStatus;
    this._doc = doc;
    this._recorderFactory = recorderFactory;
  }

  _el(tag, props = {}) {
    const el = this._doc.createElement(tag);
    Object.assign(el, props);
    return el;
  }

  /** @override */
  render(target) {
    const container = this._doc.getElementById(target);
    if (!container) return null;
    container.innerHTML = "";

    const bs =
      "width:100%;padding:11px 8px;font-size:0.9rem;line-height:1.15;border-radius:4px;border:0;cursor:pointer;color:#fff;text-align:left;";

    const col = this._el("div");
    col.style.cssText =
      "display:flex;flex-direction:column;gap:10px;max-width:320px;";

    const textEl = this._el("textarea", {
      className: "am-test-input",
      placeholder: "Say or type an agent's name to route to them…",
    });
    textEl.style.cssText = "min-height:100px;";

    const sendBtn = this._el("button", { textContent: "Send" });
    sendBtn.style.cssText = `${bs}background:#4c6ef5;`;

    const controlsRow = this._el("div");
    controlsRow.style.cssText = "display:flex;align-items:center;gap:8px;";
    const recordBtn = this._el("button", {
      className: "voice-btn",
      textContent: "Start Recording",
    });
    recordBtn.style.cssText = `${bs}flex:1;background:#28a745;`;
    const listenBtn = this._el("button", {
      className: "voice-btn",
      textContent: "Start Listening",
    });
    listenBtn.style.cssText = `${bs}flex:1;background:#17a2b8;`;
    controlsRow.append(recordBtn, listenBtn);

    const autoSendBtn = this._el("button", { textContent: "Auto Send" });
    autoSendBtn.style.cssText = `${bs}background:#6c757d;`;
    const statusEl = this._el("div");
    statusEl.style.cssText = "min-height:1.4em;font-size:0.9rem;color:#555;";

    col.append(textEl, sendBtn, controlsRow, autoSendBtn, statusEl);
    container.append(col);

    let autoSendOn = false;
    let routed = false; // once true, further speech appends to the routed agent instead of re-classifying
    let activeAgentApi = null;
    let committed = "";

    const showStatus = (msg, isError) => {
      statusEl.style.color = isError ? "#c0392b" : "#555";
      statusEl.textContent = msg;
    };

    // ── Model selector for the router's own classifier agent ───────────────
    const modelPlaceholder = this._el("div");
    col.prepend(modelPlaceholder);
    this._http
      .getJSON("/api/router-agent")
      .then((d) => {
        if (!d?.ok || !d.agent_id) return;
        const { row } = buildModelRow({
          el: this._el.bind(this),
          http: this._http,
          agentId: d.agent_id,
          showStatus,
        });
        modelPlaceholder.replaceWith(row);
      })
      .catch(() => {});

    autoSendBtn.addEventListener("click", () => {
      autoSendOn = !autoSendOn;
      autoSendBtn.style.background = autoSendOn ? "#2f55e7" : "#6c757d";
      autoSendBtn.style.fontWeight = autoSendOn ? "700" : "";
    });

    // ── Detection / routing ─────────────────────────────────────────────────
    const routeTo = async (agentName, remainder) => {
      const id = this._resolveAgentId(agentName);
      if (!id) {
        showStatus(
          `Detected "${agentName}" but couldn't find that agent.`,
          true,
        );
        return;
      }
      const api = await this._openAgent(id);
      if (api?.setText) api.setText(remainder || "");
      activeAgentApi = api;
      routed = true;
      textEl.value = "";
      committed = "";
      showStatus(`Routed to ${agentName}.`);
    };

    // manual=true (typed Send, or a completed Start-Recording clip with Auto
    // Send on): silence is reported as an error. manual=false (live listening
    // chunks): most speech won't yet contain a name, so stay quiet instead of
    // erroring on every phrase.
    const runDetection = async (text, { manual = false } = {}) => {
      const trimmed = (text || "").trim();
      if (!trimmed) {
        if (manual) showStatus("Nothing to send.", true);
        return;
      }
      if (manual) showStatus("Detecting agent…");
      let result;
      try {
        result = await this._http.postJSON("/api/route-detect", {
          text: trimmed,
        });
      } catch (e) {
        if (manual) showStatus(`Detection failed: ${e.message}`, true);
        return;
      }
      if (!result?.ok || !result.agent) {
        if (manual) {
          showStatus(
            "No agent addressed yet — say or type an agent's name to route this.",
            true,
          );
        }
        return;
      }
      await routeTo(result.agent, result.remainder);
    };

    sendBtn.addEventListener("click", () =>
      runDetection(textEl.value, { manual: true }),
    );

    // ── Start Recording (identical wiring to InputOptionsRenderer's voice
    // button, just relabeled and pointed at runDetection instead of a fixed
    // agent's Send) ──────────────────────────────────────────────────────────
    const recorder = this._recorderFactory({
      onStateChange: (state) => {
        const recording = state === RecorderState.RECORDING;
        recordBtn.classList.toggle("recording", recording);
        recordBtn.textContent = recording
          ? "Stop Recording"
          : "Start Recording";
        recordBtn.disabled = state === RecorderState.PROCESSING;
        listenBtn.disabled = state !== RecorderState.IDLE;
      },
    });
    recordBtn.addEventListener("click", async () => {
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
        if (autoSendOn) await runDetection(textEl.value, { manual: true });
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

    // ── Start Listening (continuous, browser-native) ───────────────────────
    const syncListenBtn = (state) => {
      const listening = state === ListenerState.LISTENING;
      listenBtn.classList.toggle("recording", listening);
      listenBtn.textContent = listening ? "Stop Listening" : "Start Listening";
      recordBtn.disabled = listening;
    };
    const handleResult = (text, isFinal) => {
      if (routed) {
        if (isFinal) activeAgentApi?.appendText?.(text);
        return;
      }
      if (!isFinal) {
        textEl.value = committed ? `${committed} ${text}` : text;
        return;
      }
      committed = committed ? `${committed} ${text}` : text;
      textEl.value = committed;
      runDetection(committed, { manual: false });
    };
    this._listener.setCallbacks({
      onStateChange: syncListenBtn,
      onResult: handleResult,
    });
    syncListenBtn(this._listener.state); // reflect state if already listening
    listenBtn.addEventListener("click", async () => {
      if (this._listener.isListening) {
        this._listener.stop();
      } else {
        showStatus("Listening…");
        const ok = await this._listener.start();
        if (!ok)
          showStatus(
            "Speech recognition isn't available in this browser.",
            true,
          );
      }
    });

    return { runDetection, recorder, listener: this._listener };
  }
}
