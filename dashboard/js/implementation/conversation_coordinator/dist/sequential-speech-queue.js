/** Serializes playback while allowing the agent to keep producing sentences. */
export class SequentialSpeechQueue {
  states = new Map();
  speech;
  session;
  constructor({ speech, session = null }) {
    if (!speech) throw new Error("SequentialSpeechQueue requires speech");
    this.speech = speech;
    this.session = session;
  }
  enqueue(segment, agentName) {
    let state = this.states.get(segment.generationId);
    if (!state) {
      state = {
        chain: Promise.resolve(),
        cancelled: false,
        expectedSequence: 0,
        current: null,
        pendingCount: 0,
        finishing: false,
      };
      this.states.set(segment.generationId, state);
    }
    if (state.cancelled || segment.sequence !== state.expectedSequence) return;
    state.expectedSequence += 1;
    state.pendingCount += 1;
    state.chain = state.chain.then(async () => {
      if (state?.cancelled) return;
      const playback = this.speech.speak(segment.text, agentName);
      if (!playback) return;
      state.current = playback;
      this.session?.trackPlayback?.(segment.generationId, {
        cancel: () => this.cancel(segment.generationId),
      });
      const completion =
        playback.finished ?? playback.pending ?? Promise.resolve();
      void completion.then(() => {
        if (state?.cancelled) return;
        state.pendingCount -= 1;
        if (state.finishing && state.pendingCount === 0)
          this.session?.completeTurn?.(segment.generationId);
      });
      const engine = await (playback.pending ?? Promise.resolve(true));
      if (!engine && this.speech.lastError)
        throw new Error(`voice playback failed: ${this.speech.lastError}`);
      if (state?.cancelled) {
        playback.cancel?.();
        return;
      }
      await (playback.finished ?? Promise.resolve());
      state.current = null;
    });
  }
  async finish(generationId) {
    const state = this.states.get(generationId);
    if (!state) return;
    state.finishing = true;
    if (state.pendingCount === 0) this.session?.completeTurn?.(generationId);
    try {
      await state.chain;
    } finally {
      this.states.delete(generationId);
    }
  }
  cancel(generationId) {
    const state = this.states.get(generationId);
    if (state) state.cancelled = true;
    this.states.delete(generationId);
    if (state) {
      if (this.speech.cancel) this.speech.cancel();
      else state.current?.cancel?.();
    }
  }
}
