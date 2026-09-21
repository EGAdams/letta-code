import type {
  AgentEvent as ExistingAgentEvent,
  ConversationTurn as ExistingConversationTurn,
} from "../../conversation-agent.interface.js";
import type {
  GenerationId,
  SessionStateValue,
} from "../../voice_session/dist/voice-session.js";

export type { GenerationId };

/** Public event kinds produced by a conversation adapter. */
export type AgentEventKind =
  | "assistant_text"
  | "reasoning"
  | "tool_call"
  | "tool_result"
  | "status"
  | "terminal";

/** Provider neutral input for one agent turn. */
export type ConversationTurn = ExistingConversationTurn;

/** Provider neutral output from one agent turn. */
export interface AgentEvent
  extends Omit<ExistingAgentEvent, "kind" | "detail"> {
  kind: AgentEventKind;
  text: string;
  generationId: GenerationId;
  name?: string;
  detail?: Readonly<Record<string, unknown>> | null;
}

/** Existing conversation adapter boundary, expressed structurally for TS. */
export interface ConversationAgentPort {
  submit(
    turn: ConversationTurn,
    generationId: GenerationId,
  ): AsyncIterable<AgentEvent>;
  cancel(generationId: GenerationId): void;
}

/** The subset of VoiceSession used by the coordinator. */
export interface VoiceSessionPort {
  readonly state: SessionStateValue;
  readonly currentGeneration: GenerationId | null;
  startListening(): string;
  beginTurn(): GenerationId;
  beginSpeaking(generationId: unknown): boolean;
  completeTurn(generationId: unknown): boolean;
  interrupt(): GenerationId | null;
  close(): void;
  accepts(generationId: unknown): generationId is GenerationId;
}

/** Result of the existing SpokenOutputPolicy gate. */
export interface SpeechVerdict {
  readonly speak: boolean;
  readonly reason: string;
  readonly text: string;
}

/** Only current public assistant text passes this policy. */
export interface SpokenOutputPolicyPort {
  admit(event: AgentEvent): SpeechVerdict;
}

/** One sentence ready for ordered synthesis and playback. */
export interface SpeechSegment {
  readonly generationId: GenerationId;
  readonly sequence: number;
  readonly text: string;
  readonly final: boolean;
}

/**
 * Strategy for deterministic sentence boundaries.
 *
 * It receives normalized deltas, not provider snapshots. `flush` releases the
 * final unterminated phrase when the agent emits a terminal event.
 */
export interface SentenceSegmenterPort {
  push(delta: string): readonly string[];
  flush(): string | null;
  reset(): void;
}

/**
 * Ordered, cancellable output boundary.
 *
 * A concrete queue may prepare sentence N+1 while sentence N is playing, but
 * it must play segments in sequence and reject cancelled generations.
 */
export interface SpeechQueuePort {
  enqueue(segment: SpeechSegment, agentName: string): void;
  finish(generationId: GenerationId): Promise<void>;
  cancel(generationId: GenerationId): void;
}

/** UI and telemetry observer; the coordinator contains no DOM operations. */
export interface ConversationCoordinatorObserver {
  onEvent?(event: AgentEvent): void;
  onAssistantDelta?(generationId: GenerationId, text: string): void;
  onSpeechQueued?(segment: SpeechSegment): void;
  onTurnComplete?(outcome: ConversationTurnOutcome): void;
  onError?(generationId: GenerationId | null, error: Error): void;
}

export type ConversationTurnStatus = "completed" | "interrupted" | "failed";

export interface ConversationTurnOutcome {
  readonly generationId: GenerationId;
  readonly status: ConversationTurnStatus;
  readonly text: string;
  readonly spokenSegments: number;
}

export interface ConversationCoordinatorDependencies {
  readonly agent: ConversationAgentPort;
  readonly session: VoiceSessionPort;
  readonly spokenOutputPolicy: SpokenOutputPolicyPort;
  readonly sentenceSegmenter: SentenceSegmenterPort;
  readonly speechQueue: SpeechQueuePort;
  readonly observer?: ConversationCoordinatorObserver;
}

export interface ConversationTurnOptions {
  readonly agentName: string;
  readonly speak: boolean;
}

/** Mediator contract for a single conversational surface. */
export interface ConversationCoordinatorPort {
  start(
    turn: ConversationTurn,
    options: ConversationTurnOptions,
  ): Promise<ConversationTurnOutcome>;
  interrupt(): GenerationId | null;
  close(): void;
}

const SENTENCE_END = /[.!?]["')\]]?(?=\s)/u;
const NON_TERMINAL_ABBREVIATION =
  /(?:\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc)|\b[A-Z])\.$/u;

/** Deterministic Strategy that turns arbitrary text deltas into speakable phrases. */
export class DeterministicSentenceSegmenter implements SentenceSegmenterPort {
  private buffer = "";

  constructor(private readonly maxCharacters = 220) {
    if (!Number.isInteger(maxCharacters) || maxCharacters < 40)
      throw new Error("Sentence segment length must be at least 40 characters");
  }

  push(delta: string): readonly string[] {
    if (typeof delta !== "string" || !delta) return [];
    this.buffer += delta;
    const complete: string[] = [];
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

  flush(): string | null {
    const tail = this.buffer.trim();
    this.buffer = "";
    return tail || null;
  }

  reset(): void {
    this.buffer = "";
  }

  private takeSentence(): string | null {
    for (const match of this.buffer.matchAll(new RegExp(SENTENCE_END, "gu"))) {
      const end = (match.index ?? 0) + match[0].length;
      const candidate = this.buffer.slice(0, end).trim();
      if (!candidate || NON_TERMINAL_ABBREVIATION.test(candidate)) continue;
      this.buffer = this.buffer.slice(end).replace(/^\s+/u, "");
      return candidate;
    }
    return null;
  }

  private takeLengthBoundedPhrase(): string | null {
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
export class ConversationCoordinator implements ConversationCoordinatorPort {
  private activeGeneration: GenerationId | null = null;
  private closed = false;

  constructor(
    private readonly dependencies: ConversationCoordinatorDependencies,
  ) {}

  async start(
    turn: ConversationTurn,
    options: ConversationTurnOptions,
  ): Promise<ConversationTurnOutcome> {
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

    const queueText = (segmentText: string, final: boolean) => {
      if (!options.speak || !segmentText.trim()) return;
      if (spokenSegments === 0 && !session.beginSpeaking(generationId)) return;
      const segment: SpeechSegment = {
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
      const outcome: ConversationTurnOutcome = {
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

  interrupt(): GenerationId | null {
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

  close(): void {
    if (this.closed) return;
    this.interrupt();
    this.dependencies.session.close();
    this.closed = true;
  }
}
