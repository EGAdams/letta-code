export class ManualClock {
  constructor(public value = 0) {}

  now(): number {
    return this.value;
  }

  set(value: number): void {
    this.value = value;
  }
}

export class SequentialTraceIds {
  private current = 0;

  next(): string {
    this.current += 1;
    return `trace-${this.current}`;
  }
}

export class RecordingSink {
  reports: unknown[] = [];

  publish(report: unknown): void {
    this.reports.push(report);
  }
}

export const context = {
  sessionId: "session-1",
  generationId: "generation-1",
  agentId: "toyota",
  inputMode: "push_to_talk",
} as const;

export async function loadSubject() {
  return import("../src/conversation-latency-observer.ts");
}

export async function observerFixture(startedAtMs = 0) {
  const subject = await loadSubject();
  const clock = new ManualClock(startedAtMs);
  const sink = new RecordingSink();
  const traceIds = new SequentialTraceIds();
  const observer = new subject.ConversationLatencyObserver({
    clock,
    sink,
    traceIds,
  });
  return { subject, clock, sink, traceIds, observer };
}
