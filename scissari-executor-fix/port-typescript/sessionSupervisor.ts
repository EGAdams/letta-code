/**
 * F7 — session/transport resilience, TypeScript port for lettabot (Win11).
 *
 * Drop-in for `100.72.158.63:/home/adamsl/lettabot/src/core/`. This mirrors the
 * Python reference in `scissari_executor/session/` (29 pytest cases) so the
 * behaviour is identical and already specified by tests.
 *
 * It fixes the two F7 bugs:
 *   (a) the blind 300_000ms stream-inactivity timer killing healthy-but-slow
 *       tool calls  -> SessionHealth gives a tool call its OWN deadline.
 *   (b) the heartbeat writing to a dead subprocess (pid=undefined) and throwing
 *       'Transport not connected' -> ResilientTransport re-spawns once on send.
 *
 * Wire it up per WIRING.md.
 */

export enum StreamEventKind {
  Reasoning = "reasoning",
  Text = "text",
  ToolCallStart = "tool_call_start",
  ToolReturn = "tool_return",
  TurnEnd = "turn_end",
}

export enum SessionState {
  Idle = "idle",
  Streaming = "streaming",
  ToolCall = "tool_call",
  Closed = "closed",
  Dead = "dead",
}

export enum CloseReason {
  None = "none",
  StreamIdle = "stream_idle",
  ToolCallDeadline = "tool_call_deadline",
  TransportDead = "transport_dead",
}

export interface SessionVerdict {
  shouldClose: boolean;
  state: SessionState;
  reason: CloseReason;
  secondsSinceLastEvent: number;
  secondsInToolCall: number;
  detail: string;
}

const DEFAULT_STREAM_IDLE_S = 300; // lettabot's current single coarse timer (the bug)
const DEFAULT_TOOL_CALL_DEADLINE_S = 900; // a big executor_run gets its own budget

const nowS = () => Date.now() / 1000;

/** State machine: is the agent actually hung, or just mid-tool-call? */
export class SessionHealth {
  private state = SessionState.Idle;
  private lastEventAt: number;
  private toolCallStartedAt: number | null = null;

  constructor(
    private readonly streamIdleS = DEFAULT_STREAM_IDLE_S,
    private readonly toolDeadlineS = DEFAULT_TOOL_CALL_DEADLINE_S,
    private readonly clock: () => number = nowS,
  ) {
    this.lastEventAt = this.clock();
  }

  get inToolCall() {
    return this.state === SessionState.ToolCall;
  }
  get toolCallStart() {
    return this.toolCallStartedAt;
  }
  get lastEvent() {
    return this.lastEventAt;
  }
  get streamIdle() {
    return this.streamIdleS;
  }
  get toolDeadline() {
    return this.toolDeadlineS;
  }

  onEvent(kind: StreamEventKind, at: number = this.clock()): void {
    this.lastEventAt = at;
    if (kind === StreamEventKind.ToolCallStart) {
      this.state = SessionState.ToolCall;
      this.toolCallStartedAt = at;
    } else if (kind === StreamEventKind.ToolReturn) {
      this.state = SessionState.Streaming;
      this.toolCallStartedAt = null;
    } else if (kind === StreamEventKind.TurnEnd) {
      this.state = SessionState.Idle;
      this.toolCallStartedAt = null;
    } else if (this.state !== SessionState.ToolCall) {
      this.state = SessionState.Streaming;
    }
  }

  shouldClose(at: number = this.clock()): SessionVerdict {
    const sinceEvent = at - this.lastEventAt;
    if (
      this.state === SessionState.ToolCall &&
      this.toolCallStartedAt !== null
    ) {
      const inTool = at - this.toolCallStartedAt;
      if (inTool >= this.toolDeadlineS) {
        return {
          shouldClose: true,
          state: this.state,
          reason: CloseReason.ToolCallDeadline,
          secondsSinceLastEvent: sinceEvent,
          secondsInToolCall: inTool,
          detail: `tool call exceeded its ${this.toolDeadlineS}s budget`,
        };
      }
      return {
        shouldClose: false,
        state: this.state,
        reason: CloseReason.None,
        secondsSinceLastEvent: sinceEvent,
        secondsInToolCall: inTool,
        detail: "tool call in flight — stream silence is expected",
      };
    }
    if (sinceEvent >= this.streamIdleS) {
      return {
        shouldClose: true,
        state: this.state,
        reason: CloseReason.StreamIdle,
        secondsSinceLastEvent: sinceEvent,
        secondsInToolCall: 0,
        detail: `no stream activity for ${Math.round(sinceEvent)}s`,
      };
    }
    return {
      shouldClose: false,
      state: this.state,
      reason: CloseReason.None,
      secondsSinceLastEvent: sinceEvent,
      secondsInToolCall: 0,
      detail: "",
    };
  }
}

/** Observer: suppress the inactivity timer while a tool call runs. */
export class ToolCallKeepalive {
  constructor(private readonly health: SessionHealth) {}
  isSuppressed() {
    return this.health.inToolCall;
  }
  nextDeadline(): number {
    if (this.health.inToolCall && this.health.toolCallStart !== null) {
      return this.health.toolCallStart + this.health.toolDeadline;
    }
    return this.health.lastEvent + this.health.streamIdle;
  }
}

/** The raw SDK SubprocessTransport surface we depend on. */
export interface ISubprocessTransport {
  readonly pid: number | undefined;
  readonly closed: boolean;
  spawn(): void | Promise<void>;
  write(data: string): void; // throws 'Transport not connected' when dead
}

export class TransportUnavailableError extends Error {}

/** Minimal circuit breaker (mirrors scissari_executor/breaker.py). */
class RespawnBreaker {
  private consecutive = 0;
  private openedAt: number | null = null;
  constructor(
    private readonly threshold = 3,
    private readonly resetAfterS = 30,
  ) {}
  allow(): boolean {
    if (this.openedAt === null) return true;
    if (nowS() - this.openedAt >= this.resetAfterS) {
      this.openedAt = null;
      this.consecutive = 0;
      return true;
    }
    return false;
  }
  recordSuccess() {
    this.consecutive = 0;
    this.openedAt = null;
  }
  recordFailure() {
    this.consecutive += 1;
    if (this.consecutive >= this.threshold) this.openedAt = nowS();
  }
}

/** Proxy/Decorator: re-spawn a dead subprocess on send() instead of throwing. */
export class ResilientTransport {
  public respawns = 0;
  constructor(
    private readonly inner: ISubprocessTransport,
    private readonly breaker = new RespawnBreaker(),
  ) {}

  private alive() {
    return this.inner.pid !== undefined && !this.inner.closed;
  }

  async send(data: string): Promise<void> {
    if (this.alive()) {
      this.inner.write(data);
      this.breaker.recordSuccess();
      return;
    }
    if (!this.breaker.allow()) {
      throw new TransportUnavailableError(
        "executor subprocess is down and the respawn circuit is open — alerting ops instead of spinning",
      );
    }
    try {
      await this.inner.spawn();
      this.respawns += 1;
    } catch (e) {
      this.breaker.recordFailure();
      throw new TransportUnavailableError(
        `re-spawn failed: ${(e as Error).message}`,
      );
    }
    if (!this.alive()) {
      this.breaker.recordFailure();
      throw new TransportUnavailableError(
        "re-spawn did not produce a live subprocess",
      );
    }
    this.inner.write(data);
    this.breaker.recordSuccess();
  }
}

export interface AlertSink {
  emit(message: string): void | Promise<void>;
}

/** Facade the bot + heartbeat call instead of touching the raw SDK session. */
export class SessionSupervisor {
  private readonly health: SessionHealth;
  readonly keepalive: ToolCallKeepalive;

  constructor(
    private readonly transport: ResilientTransport,
    private readonly alert: AlertSink,
    private readonly agentId = "scissari",
    health?: SessionHealth,
  ) {
    this.health = health ?? new SessionHealth();
    this.keepalive = new ToolCallKeepalive(this.health);
  }

  feedEvent(kind: StreamEventKind, at?: number) {
    this.health.onEvent(kind, at);
  }

  async tick(at?: number): Promise<SessionVerdict> {
    const v = this.health.shouldClose(at);
    if (v.shouldClose) await this.alert.emit(this.explain(v));
    return v;
  }

  async send(data: string): Promise<void> {
    await this.transport.send(data);
  }

  private explain(v: SessionVerdict): string {
    if (v.reason === CloseReason.ToolCallDeadline) {
      return `closing session: tool call ran ${Math.round(v.secondsInToolCall)}s, past its deadline (${v.detail})`;
    }
    if (v.reason === CloseReason.StreamIdle)
      return `closing session: ${v.detail}`;
    return "closing session";
  }
}
