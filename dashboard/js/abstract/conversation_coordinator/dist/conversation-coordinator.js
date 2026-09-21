const SENTENCE_END = /[.!?]["')\]]?(?=\s)/u;
const NON_TERMINAL_ABBREVIATION =
  /(?:\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc)|\b[A-Z])\.$/u;
const CHUNK_END_SENTENCE = /[.!?]["')\]]?$/u;
const CHUNK_END_NUMBER = /\d\.$/u;
/** Deterministic Strategy that turns arbitrary text deltas into speakable phrases. */
export class DeterministicSentenceSegmenter {
  maxCharacters;
  buffer = "";
  constructor(maxCharacters = 220) {
    this.maxCharacters = maxCharacters;
    if (!Number.isInteger(maxCharacters) || maxCharacters < 40)
      throw new Error("Sentence segment length must be at least 40 characters");
  }
  push(delta) {
    if (typeof delta !== "string" || !delta) return [];
    this.buffer += delta;
    const complete = [];
    while (true) {
      const sentence = this.takeSentence();
      if (sentence) {
        complete.push(sentence);
        continue;
      }
      const fallback = this.takeLengthBoundedPhrase();
      if (fallback) {
        complete.push(fallback);
        continue;
      }
      break;
    }
    return complete;
  }
  flush() {
    const tail = this.buffer.trim();
    this.buffer = "";
    return tail || null;
  }
  reset() {
    this.buffer = "";
  }
  takeSentence() {
    for (const match of this.buffer.matchAll(new RegExp(SENTENCE_END, "gu"))) {
      const end = (match.index ?? 0) + match[0].length;
      const candidate = this.buffer.slice(0, end).trim();
      if (!candidate || NON_TERMINAL_ABBREVIATION.test(candidate)) continue;
      this.buffer = this.buffer.slice(end).replace(/^\s+/u, "");
      return candidate;
    }
    const candidate = this.buffer.trim();
    if (
      candidate &&
      CHUNK_END_SENTENCE.test(candidate) &&
      !CHUNK_END_NUMBER.test(candidate) &&
      !NON_TERMINAL_ABBREVIATION.test(candidate)
    ) {
      this.buffer = "";
      return candidate;
    }
    return null;
  }
  takeLengthBoundedPhrase() {
    if (this.buffer.length <= this.maxCharacters) return null;
    const window = this.buffer.slice(0, this.maxCharacters + 1);
    const splitAt = Math.max(window.lastIndexOf(", "), window.lastIndexOf(" "));
    if (splitAt < 1) return null;
    const phrase = this.buffer
      .slice(0, splitAt + (window[splitAt] === "," ? 1 : 0))
      .trim();
    this.buffer = this.buffer.slice(splitAt + 1).replace(/^\s+/u, "");
    return phrase || null;
  }
}
/** Mediator for agent streaming, turn fencing, segmentation, and ordered speech. */
export class ConversationCoordinator {
  dependencies;
  activeGeneration = null;
  closed = false;
  constructor(dependencies) {
    this.dependencies = dependencies;
  }
  async start(turn, options) {
    if (this.closed) throw new Error("ConversationCoordinator is closed");
    this.interrupt();
    const { agent, session, sentenceSegmenter, speechQueue, observer } =
      this.dependencies;
    if (session.state !== "listening") session.startListening();
    const generationId = session.beginTurn();
    this.activeGeneration = generationId;
    sentenceSegmenter.reset();
    let text = "";
    let spokenSegments = 0;
    let sawTerminal = false;
    const queueText = (segmentText, final) => {
      if (!options.speak || !segmentText.trim()) return;
      if (spokenSegments === 0 && !session.beginSpeaking(generationId)) return;
      const segment = {
        generationId,
        sequence: spokenSegments,
        text: segmentText.trim(),
        final,
      };
      spokenSegments += 1;
      speechQueue.enqueue(segment, options.agentName);
      observer?.onSpeechQueued?.(segment);
    };
    try {
      for await (const event of agent.submit(turn, generationId)) {
        if (!session.accepts(generationId)) break;
        if (event.generationId !== generationId) continue;
        observer?.onEvent?.(event);
        if (event.kind === "terminal") {
          sawTerminal = true;
          const tail = sentenceSegmenter.flush();
          if (tail) queueText(tail, true);
          break;
        }
        const verdict = this.dependencies.spokenOutputPolicy.admit(event);
        if (event.kind !== "assistant_text" || !verdict.speak) continue;
        text += event.text;
        observer?.onAssistantDelta?.(generationId, event.text);
        for (const sentence of sentenceSegmenter.push(event.text))
          queueText(sentence, false);
      }
      if (!session.accepts(generationId)) {
        return { generationId, status: "interrupted", text, spokenSegments };
      }
      if (!sawTerminal) {
        const tail = sentenceSegmenter.flush();
        if (tail) queueText(tail, true);
      }
      if (!text.trim()) throw new Error("Agent returned no answer.");
      const outcome = {
        generationId,
        status: "completed",
        text,
        spokenSegments,
      };
      if (spokenSegments > 0) {
        void speechQueue.finish(generationId).then(
          () => {
            if (session.accepts(generationId))
              session.completeTurn(generationId);
            if (this.activeGeneration === generationId)
              this.activeGeneration = null;
            observer?.onTurnComplete?.(outcome);
          },
          (cause) => {
            const error =
              cause instanceof Error ? cause : new Error(String(cause));
            if (session.accepts(generationId))
              session.completeTurn(generationId);
            if (this.activeGeneration === generationId)
              this.activeGeneration = null;
            observer?.onError?.(generationId, error);
          },
        );
      } else {
        session.completeTurn(generationId);
        this.activeGeneration = null;
        observer?.onTurnComplete?.(outcome);
      }
      return outcome;
    } catch (cause) {
      if (!session.accepts(generationId)) {
        return { generationId, status: "interrupted", text, spokenSegments };
      }
      speechQueue.cancel(generationId);
      session.completeTurn(generationId);
      this.activeGeneration = null;
      const error = cause instanceof Error ? cause : new Error(String(cause));
      observer?.onError?.(generationId, error);
      throw error;
    }
  }
  interrupt() {
    const generationId =
      this.activeGeneration ?? this.dependencies.session.currentGeneration;
    if (!generationId) return null;
    this.dependencies.agent.cancel(generationId);
    this.dependencies.speechQueue.cancel(generationId);
    const interrupted = this.dependencies.session.interrupt();
    this.dependencies.sentenceSegmenter.reset();
    this.activeGeneration = null;
    return interrupted;
  }
  close() {
    if (this.closed) return;
    this.interrupt();
    this.dependencies.session.close();
    this.closed = true;
  }
}
