/**
 * AgentVoiceCatalog — Strategy/Registry mapping agent names to a preferred
 * SpeechSynthesisVoice, so each agent's replies are read in a distinct voice.
 *
 * Pure policy (no DOM, no `speechSynthesis`): given the live `voices` array
 * from `SpeechSynthesis.getVoices()`, it resolves and caches one voice per
 * agent name. Resolution order per agent:
 *   1. The agent's preferred name patterns (first match wins, preferring a
 *      voice not already claimed by another agent).
 *   2. Any unused female-sounding English voice.
 *   3. Any female-sounding English voice (reuse beats falling through to male).
 *   4. Any unused English voice that is not identifiably male.
 *   5. Any English voice that is not identifiably male.
 *   6. The shared `fallback` voice (or the first available voice).
 *
 * Steps 3–5 implement the "never fall back to a male voice" rule (commit
 * b18052fa): reusing a female voice another agent already has is preferable to
 * picking an identifiably-male one. Once a voice is assigned to an agent it is
 * cached for the session so the agent keeps the same voice even if
 * `getVoices()` is re-queried.
 */

/** Matches common female-sounding TTS voice names across platforms. */
export const FEMALE_VOICE_RE =
  /female|\b(zira|aria|jenny|samantha|susan|victoria|karen|moira|tessa|allison|ava|joanna|salli|kendra|kimberly|ivy|emma|olivia|amy|michelle|ashley|ana|cora|elizabeth|sara|nancy|monica|libby|sonia|catherine|fiona|natasha|hazel|maisie|google us english)\b/i;

/**
 * Matches common male-sounding TTS voice names. Used to keep the fallback
 * chain from ever landing on a male voice when no female voice is available.
 */
export const MALE_VOICE_RE =
  /\bmale\b|\b(david|mark|guy|davis|tony|jacob|andrew|brian|christopher|eric|roger|steffan|james|william|daniel|liam|ryan|george|thomas)\b/i;

/** Default per-agent voice preferences (first matching pattern wins). */
export const DEFAULT_AGENT_VOICE_PREFERENCES = {
  Scissari: [/zira/i],
  Mazda: [/aria/i],
  Frita: [/jenny|joanna/i],
  Hailey: [/samantha|susan/i],
  Jeri: [/salli|kendra|amy|emma|olivia/i],
  Cesare: [/ashley|michelle/i],
  "Mazda Router": [/ana/i],
  "Mazda Parser": [/cora/i],
  "Mazda Vendor Identity": [/elizabeth/i],
  "Mazda Receipt Linker": [/sara/i],
  "Mazda Categorization": [/nancy|monica/i],
};

export class AgentVoiceCatalog {
  /** @param {Record<string, RegExp[]>} [preferences] */
  constructor(preferences = DEFAULT_AGENT_VOICE_PREFERENCES) {
    this._preferences = preferences;
    this._cache = new Map();
  }

  /**
   * Resolve (and cache) the voice to use for `agentName`.
   * @param {string|null|undefined} agentName
   * @param {SpeechSynthesisVoice[]} voices
   * @param {SpeechSynthesisVoice|null} [fallback] used when nothing else matches
   * @returns {SpeechSynthesisVoice|null}
   */
  voiceFor(agentName, voices, fallback = null) {
    if (!voices || !voices.length) return fallback;
    if (!agentName) return fallback || voices[0];

    const cached = this._cache.get(agentName);
    if (cached && voices.includes(cached)) return cached;

    const picked = this._resolve(agentName, voices, fallback);
    if (picked) this._cache.set(agentName, picked);
    return picked;
  }

  /** Forget any cached voice assignments (e.g. when the voice list changes). */
  reset() {
    this._cache.clear();
  }

  _resolve(agentName, voices, fallback) {
    const used = new Set(this._cache.values());
    const unused = (pred) => voices.find((v) => pred(v) && !used.has(v));

    for (const pattern of this._preferences[agentName] || []) {
      const match =
        unused((v) => pattern.test(v.name)) ||
        voices.find((v) => pattern.test(v.name));
      if (match) return match;
    }

    return (
      // Prefer a female voice nobody else is using yet...
      unused((v) => /en/i.test(v.lang) && FEMALE_VOICE_RE.test(v.name)) ||
      // ...but reusing a female voice beats falling through to a male one.
      voices.find((v) => /en/i.test(v.lang) && FEMALE_VOICE_RE.test(v.name)) ||
      // No identifiably-female voice at all: pick anything not identifiably male.
      unused((v) => /en/i.test(v.lang) && !MALE_VOICE_RE.test(v.name)) ||
      voices.find((v) => /en/i.test(v.lang) && !MALE_VOICE_RE.test(v.name)) ||
      fallback ||
      voices[0]
    );
  }
}
