import { AgentVoiceCatalog } from "./agent-voice-catalog.interface.js";
import { TextUtils } from "./text-utils.js";

/**
 * SpeechSynthesizer — Facade.
 *
 * The original `Speech` object was a small facade over the browser
 * SpeechSynthesis API (pick a voice, strip markdown, speak, cancel). We keep it
 * a facade but make the underlying engine an injected port so the policy
 * (voice selection, cleaning, "cancel before speaking so replies never
 * overlap") can be tested against a fake engine.
 *
 * The engine port must provide: getVoices(), speak(utterance), cancel().
 *
 * Per-agent voice selection is delegated to an injected `AgentVoiceCatalog`
 * (Strategy) — `speak(text, agentName)` looks up that agent's voice so
 * different agents are read in different voices.
 */
export class SpeechSynthesizer {
  /**
   * @param {object} [engine] SpeechSynthesis-like port. Null => unsupported.
   * @param {(text:string)=>object} [utteranceFactory] builds an utterance obj.
   * @param {AgentVoiceCatalog} [voiceCatalog] per-agent voice strategy.
   */
  constructor(
    engine = null,
    utteranceFactory = (text) => ({ text }),
    voiceCatalog = new AgentVoiceCatalog(),
  ) {
    this._engine = engine;
    this._utteranceFactory = utteranceFactory;
    this._voiceCatalog = voiceCatalog;
    this.voice = null;
  }

  /** Facade flag: is text-to-speech available at all? */
  get supported() {
    return !!this._engine;
  }

  /**
   * Choose a sensible English voice from the (async) voice list. Prefers a
   * female-sounding voice (matches the agents' established voice).
   */
  pickVoice() {
    if (!this.supported) return null;
    const voices = this._engine.getVoices() || [];
    if (!voices.length) return null;
    const FEMALE =
      /female|\b(zira|aria|jenny|samantha|susan|victoria|karen|moira|tessa|allison|ava|joanna|salli|kendra|kimberly|ivy|emma|olivia|amy)\b/i;
    this.voice =
      voices.find(
        (v) =>
          /en[-_]US/i.test(v.lang) &&
          FEMALE.test(v.name) &&
          /google|natural|neural/i.test(v.name),
      ) ||
      voices.find((v) => /en[-_]US/i.test(v.lang) && FEMALE.test(v.name)) ||
      voices.find((v) => /^en/i.test(v.lang) && FEMALE.test(v.name)) ||
      voices.find(
        (v) =>
          /en[-_]US/i.test(v.lang) && /google|natural|neural/i.test(v.name),
      ) ||
      voices.find((v) => /en[-_]US/i.test(v.lang)) ||
      voices.find((v) => /^en/i.test(v.lang)) ||
      voices[0];
    return this.voice;
  }

  /** Normalize text for reading aloud (delegates to shared util). */
  clean(text) {
    return TextUtils.stripMarkdown(text);
  }

  /**
   * Speak text. Cancels anything in flight first so replies never overlap.
   * When `agentName` is given, the catalog picks that agent's own voice
   * (falling back to the shared default voice if none is assigned).
   * Returns the utterance that was spoken, or null if nothing was said.
   */
  speak(text, agentName = null) {
    if (!this.supported) return null;
    const say = this.clean(text);
    if (!say) return null;
    this._engine.cancel();
    if (!this.voice) this.pickVoice();
    const voices = this._engine.getVoices() || [];
    const voice = this._voiceCatalog.voiceFor(agentName, voices, this.voice);
    const u = this._utteranceFactory(say);
    if (voice) u.voice = voice;
    u.rate = 1.0;
    u.pitch = 1.0;
    u.volume = 1.0;
    this._engine.speak(u);
    return u;
  }

  /** Stop any in-progress speech. */
  cancel() {
    if (this.supported) this._engine.cancel();
  }
}
