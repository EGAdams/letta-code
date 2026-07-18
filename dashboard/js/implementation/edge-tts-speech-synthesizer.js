import { BrowserSpeechSynthesizer } from "./browser-speech-synthesizer.js";

/**
 * EdgeTtsSpeechSynthesizer — the agents' "new voice": server-side edge-tts
 * (`POST /api/tts`, voice en-GB-SoniaNeural — the same voice the pickle_cpp
 * scoreboard announcements use) played through an `Audio` element.
 *
 * GoF: Decorator over the BrowserSpeechSynthesizer facade — same surface
 * (`supported` / `speak(text, agentName)` / `cancel()` / `bindVoiceChanges()`),
 * but `speak` first tries the server voice and only falls back to the
 * inherited Web Speech path when the server can't produce audio (offline,
 * edge-tts missing, non-audio reply). The cancel-before-speak "replies never
 * overlap" policy is preserved across both engines via a generation counter:
 * a newer speak() or cancel() invalidates any in-flight fetch/playback.
 *
 * `fetchFn` and `audioFactory` are injected so tests never touch the network
 * or real audio output.
 */
export class EdgeTtsSpeechSynthesizer extends BrowserSpeechSynthesizer {
  /**
   * @param {Window|object} [win] passed to the browser fallback.
   * @param {object} [opts]
   * @param {typeof fetch} [opts.fetchFn]
   * @param {(url:string)=>{play:Function,pause:Function}} [opts.audioFactory]
   * @param {string|null} [opts.voice] edge-tts voice override (null = server default).
   */
  constructor(win = globalThis, opts = {}) {
    super(win);
    this._fetchFn = opts.fetchFn || win?.fetch?.bind(win) || null;
    this._audioFactory =
      opts.audioFactory ||
      (typeof win?.Audio === "function" ? (url) => new win.Audio(url) : null);
    this._voice = opts.voice || null;
    this._audio = null;
    this._audioUrl = null;
    this._generation = 0;
  }

  /** Server TTS works without Web Speech; either engine makes us supported. */
  get supported() {
    return !!(this._fetchFn && this._audioFactory) || super.supported;
  }

  /**
   * Speak via the server voice, falling back to the browser engine. Returns a
   * `{ text, pending }` token synchronously; `pending` resolves to the engine
   * that actually spoke ("edge-tts" | "browser" | null).
   */
  speak(text, agentName = null) {
    if (!this.supported) return null;
    const say = this.clean(text);
    if (!say) return null;
    this.cancel();
    const generation = this._generation;
    const pending = this._speakRemote(say, generation).catch(() => {
      if (generation !== this._generation) return null;
      // super.speak/cancel dereference the Web Speech engine unguarded (our
      // `supported` override is true without one), so gate on the engine.
      if (!this._engine) return null;
      return super.speak(text, agentName) ? "browser" : null;
    });
    return { text: say, pending };
  }

  /** Stop server audio AND any in-flight fetch/browser speech. */
  cancel() {
    this._generation += 1;
    if (this._audio) {
      try {
        this._audio.pause();
      } catch {
        // already stopped
      }
      this._audio = null;
    }
    this._releaseUrl();
    if (this._engine) super.cancel();
  }

  async _speakRemote(say, generation) {
    if (!this._fetchFn || !this._audioFactory) throw new Error("no server tts");
    const res = await this._fetchFn("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        this._voice ? { text: say, voice: this._voice } : { text: say },
      ),
    });
    const type = res?.headers?.get?.("content-type") || "";
    if (!res || !res.ok || !type.startsWith("audio/")) {
      throw new Error(`tts unavailable (${res ? res.status : "no response"})`);
    }
    const blob = await res.blob();
    if (generation !== this._generation) return null; // superseded meanwhile
    const URLApi = this._win?.URL || globalThis.URL;
    this._audioUrl = URLApi?.createObjectURL
      ? URLApi.createObjectURL(blob)
      : null;
    const audio = this._audioFactory(this._audioUrl || "");
    this._audio = audio;
    audio.onended = () => {
      if (this._audio === audio) {
        this._audio = null;
        this._releaseUrl();
      }
    };
    await audio.play();
    return "edge-tts";
  }

  _releaseUrl() {
    if (!this._audioUrl) return;
    const URLApi = this._win?.URL || globalThis.URL;
    try {
      URLApi?.revokeObjectURL?.(this._audioUrl);
    } catch {
      // best-effort cleanup
    }
    this._audioUrl = null;
  }
}
