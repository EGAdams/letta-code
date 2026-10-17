export const LatencyMilestone = Object.freeze({
  SPEECH_ENDED: "speech_ended",
  TRANSCRIPT_READY: "transcript_ready",
  AGENT_REQUESTED: "agent_requested",
  FIRST_AGENT_DELTA: "first_agent_delta",
  FIRST_SENTENCE_QUEUED: "first_sentence_queued",
  FIRST_TTS_REQUESTED: "first_tts_requested",
  FIRST_AUDIO_READY: "first_audio_ready",
  FIRST_AUDIO_PLAYING: "first_audio_playing",
} as const);

export type LatencyMilestoneValue =
  (typeof LatencyMilestone)[keyof typeof LatencyMilestone];

export const LatencyOutcome = Object.freeze({
  COMPLETED: "completed",
  INTERRUPTED: "interrupted",
  FAILED: "failed",
} as const);

export type LatencyOutcomeValue =
  (typeof LatencyOutcome)[keyof typeof LatencyOutcome];

export type ConversationInputMode = "push_to_talk" | "continuous" | "typed";

export interface LatencyTraceContext {
  sessionId: string;
  generationId: string;
  agentId: string;
  inputMode: ConversationInputMode;
}

export interface LatencyMilestoneDetail {
  sequence?: number;
  transport?: string;
}

export interface LatencySample {
  atMs: number;
  detail?: Readonly<LatencyMilestoneDetail>;
}

export interface LatencyDurations {
  speechToTranscript?: number;
  agentToFirstDelta?: number;
  firstDeltaToSentence?: number;
  ttsToAudioReady?: number;
  audioReadyToPlayback?: number;
  agentToFirstAudio?: number;
  speechToFirstAudio?: number;
}

export interface LatencyReport {
  readonly traceId: string;
  readonly context: Readonly<LatencyTraceContext>;
  readonly outcome: LatencyOutcomeValue;
  readonly startedAtMs: number;
  readonly finishedAtMs: number;
  readonly samples: Readonly<
    Partial<Record<LatencyMilestoneValue, Readonly<LatencySample>>>
  >;
  readonly durationsMs: Readonly<LatencyDurations>;
}

export interface MonotonicClockPort {
  now(): number;
}

export interface TraceIdSourcePort {
  next(): string;
}

export interface LatencyReportSinkPort {
  publish(report: LatencyReport): void;
}

export interface ConversationLatencyObserverPort {
  begin(context: LatencyTraceContext): string;
  mark(
    traceId: string,
    milestone: LatencyMilestoneValue,
    detail?: LatencyMilestoneDetail,
  ): boolean;
  finish(traceId: string, outcome: LatencyOutcomeValue): LatencyReport | null;
  discard(traceId: string, reason: string): boolean;
}

export interface ConversationLatencyObserverDependencies {
  clock: MonotonicClockPort;
  traceIds: TraceIdSourcePort;
  sink: LatencyReportSinkPort;
}

interface ActiveTrace {
  context: LatencyTraceContext;
  startedAtMs: number;
  lastAtMs: number;
  samples: Partial<Record<LatencyMilestoneValue, LatencySample>>;
}

const MILESTONES = new Set<unknown>(Object.values(LatencyMilestone));
const OUTCOMES = new Set<unknown>(Object.values(LatencyOutcome));

function finiteTime(value: number): boolean {
  return Number.isFinite(value) && value >= 0;
}

function readClock(clock: MonotonicClockPort): number | null {
  try {
    const value = clock.now();
    return finiteTime(value) ? value : null;
  } catch {
    return null;
  }
}

function requireDependency(
  value: unknown,
  method: string,
  label: string,
): asserts value is Record<string, (...args: never[]) => unknown> {
  if (
    value === null ||
    typeof value !== "object" ||
    typeof (value as Record<string, unknown>)[method] !== "function"
  ) {
    throw new TypeError(`ConversationLatencyObserver requires ${label}`);
  }
}

function copyContext(context: LatencyTraceContext): LatencyTraceContext {
  if (
    context === null ||
    typeof context !== "object" ||
    typeof context.sessionId !== "string" ||
    !context.sessionId.trim() ||
    typeof context.generationId !== "string" ||
    !context.generationId.trim() ||
    typeof context.agentId !== "string" ||
    !context.agentId.trim() ||
    !["push_to_talk", "continuous", "typed"].includes(context.inputMode)
  ) {
    throw new TypeError("invalid latency trace context");
  }
  return {
    sessionId: context.sessionId,
    generationId: context.generationId,
    agentId: context.agentId,
    inputMode: context.inputMode,
  };
}

function copyDetail(
  detail: LatencyMilestoneDetail | undefined,
): LatencyMilestoneDetail | null | undefined {
  if (detail === undefined) return undefined;
  if (detail === null || typeof detail !== "object") return null;
  const copy: LatencyMilestoneDetail = {};
  if (detail.sequence !== undefined) {
    if (!Number.isInteger(detail.sequence) || detail.sequence < 0) return null;
    copy.sequence = detail.sequence;
  }
  if (detail.transport !== undefined) {
    if (typeof detail.transport !== "string" || !detail.transport.trim()) {
      return null;
    }
    copy.transport = detail.transport;
  }
  return copy;
}

function duration(
  samples: ActiveTrace["samples"],
  start: LatencyMilestoneValue,
  end: LatencyMilestoneValue,
): number | undefined {
  const startSample = samples[start];
  const endSample = samples[end];
  if (!startSample || !endSample) return undefined;
  const elapsed = endSample.atMs - startSample.atMs;
  return elapsed >= 0 ? elapsed : undefined;
}

function deriveDurations(samples: ActiveTrace["samples"]): LatencyDurations {
  const pairs = [
    [
      "speechToTranscript",
      LatencyMilestone.SPEECH_ENDED,
      LatencyMilestone.TRANSCRIPT_READY,
    ],
    [
      "agentToFirstDelta",
      LatencyMilestone.AGENT_REQUESTED,
      LatencyMilestone.FIRST_AGENT_DELTA,
    ],
    [
      "firstDeltaToSentence",
      LatencyMilestone.FIRST_AGENT_DELTA,
      LatencyMilestone.FIRST_SENTENCE_QUEUED,
    ],
    [
      "ttsToAudioReady",
      LatencyMilestone.FIRST_TTS_REQUESTED,
      LatencyMilestone.FIRST_AUDIO_READY,
    ],
    [
      "audioReadyToPlayback",
      LatencyMilestone.FIRST_AUDIO_READY,
      LatencyMilestone.FIRST_AUDIO_PLAYING,
    ],
    [
      "agentToFirstAudio",
      LatencyMilestone.AGENT_REQUESTED,
      LatencyMilestone.FIRST_AUDIO_PLAYING,
    ],
    [
      "speechToFirstAudio",
      LatencyMilestone.SPEECH_ENDED,
      LatencyMilestone.FIRST_AUDIO_PLAYING,
    ],
  ] as const;
  const result: LatencyDurations = {};
  for (const [name, start, end] of pairs) {
    const value = duration(samples, start, end);
    if (value !== undefined) result[name] = value;
  }
  return result;
}

function freezeSamples(
  samples: ActiveTrace["samples"],
): LatencyReport["samples"] {
  const frozen: Partial<
    Record<LatencyMilestoneValue, Readonly<LatencySample>>
  > = {};
  for (const [milestone, sample] of Object.entries(samples)) {
    const detail = sample.detail
      ? Object.freeze({ ...sample.detail })
      : undefined;
    frozen[milestone as LatencyMilestoneValue] = Object.freeze({
      atMs: sample.atMs,
      ...(detail ? { detail } : {}),
    });
  }
  return Object.freeze(frozen);
}

/** Observer for latency telemetry. It never controls conversation behavior. */
export class ConversationLatencyObserver
  implements ConversationLatencyObserverPort
{
  private readonly clock: MonotonicClockPort;
  private readonly traceIds: TraceIdSourcePort;
  private readonly sink: LatencyReportSinkPort;
  private readonly active = new Map<string, ActiveTrace>();
  private readonly issued = new Set<string>();

  constructor({
    clock,
    traceIds,
    sink,
  }: ConversationLatencyObserverDependencies) {
    requireDependency(clock, "now", "a monotonic clock");
    requireDependency(traceIds, "next", "a trace id source");
    requireDependency(sink, "publish", "a report sink");
    this.clock = clock;
    this.traceIds = traceIds;
    this.sink = sink;
  }

  begin(context: LatencyTraceContext): string {
    const copiedContext = copyContext(context);
    const traceId = this.traceIds.next();
    const startedAtMs = readClock(this.clock);
    if (
      typeof traceId !== "string" ||
      !traceId.trim() ||
      this.issued.has(traceId)
    ) {
      throw new Error("trace id source returned an invalid or active id");
    }
    if (startedAtMs === null) {
      throw new Error("monotonic clock returned an invalid time");
    }
    this.issued.add(traceId);
    this.active.set(traceId, {
      context: copiedContext,
      startedAtMs,
      lastAtMs: startedAtMs,
      samples: {},
    });
    return traceId;
  }

  mark(
    traceId: string,
    milestone: LatencyMilestoneValue,
    detail?: LatencyMilestoneDetail,
  ): boolean {
    const trace = this.active.get(traceId);
    if (!trace || !MILESTONES.has(milestone) || trace.samples[milestone]) {
      return false;
    }
    const copiedDetail = copyDetail(detail);
    if (copiedDetail === null) return false;
    const atMs = readClock(this.clock);
    if (atMs === null || atMs < trace.lastAtMs) return false;
    trace.samples[milestone] = {
      atMs,
      ...(copiedDetail === undefined ? {} : { detail: copiedDetail }),
    };
    trace.lastAtMs = atMs;
    return true;
  }

  finish(traceId: string, outcome: LatencyOutcomeValue): LatencyReport | null {
    const trace = this.active.get(traceId);
    if (!trace || !OUTCOMES.has(outcome)) return null;
    this.active.delete(traceId);
    const observedTime = readClock(this.clock);
    const finishedAtMs =
      observedTime !== null && observedTime >= trace.lastAtMs
        ? observedTime
        : trace.lastAtMs;
    const report: LatencyReport = Object.freeze({
      traceId,
      context: Object.freeze({ ...trace.context }),
      outcome,
      startedAtMs: trace.startedAtMs,
      finishedAtMs,
      samples: freezeSamples(trace.samples),
      durationsMs: Object.freeze(deriveDurations(trace.samples)),
    });
    try {
      this.sink.publish(report);
    } catch {
      // Telemetry is observational and must never break a conversation turn.
    }
    return report;
  }

  discard(traceId: string, _reason: string): boolean {
    return this.active.delete(traceId);
  }
}
