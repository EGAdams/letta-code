// Hard deadline for one Claude SDK session.
//
// WHY THIS EXISTS: `@instantlyeasy/claude-code-sdk-ts@0.3.3`'s fluent
// `.withTimeout(ms)` only stores `options.timeout` — nothing in the query path
// (`SubprocessCLITransport.connect` / `SubprocessAbortHandler`) ever reads it.
// The only abort channel the SDK actually honours is `.withSignal(signal)`.
// So a `claude` child that stops producing output hangs `asText()` forever:
// the Trainer's watchdog loop never regains control, the codex fallback never
// fires, no emergency report is written, and `/api/intake-status` is never
// published — the intake silently stays unverified.
//
// Verified 2026-07-31 with a stub `claude` on PATH that reads stdin then sleeps:
// `.withTimeout(2000)` returned only after the stub exited at 30s.
//
// Belt and braces: we abort the signal (the SDK cancels the child, then SIGKILLs
// it after 5s) AND reject on our own timer, so the caller regains control even
// if the SDK's stream never settles after the cancel.

export class ClaudeAttemptTimeoutError extends Error {
  readonly timeoutMs: number;

  constructor(timeoutMs: number) {
    super(
      `Claude Trainer session exceeded its ${timeoutMs}ms attempt deadline`,
    );
    this.name = "ClaudeAttemptTimeoutError";
    this.timeoutMs = timeoutMs;
  }
}

export type AbortableRun<T> = (signal: AbortSignal) => Promise<T>;

/**
 * Run `run` with a real deadline. `run` receives an AbortSignal that must be
 * handed to the SDK via `.withSignal(...)`.
 *
 * Resolves with `run`'s value when it finishes in time; rejects with
 * `ClaudeAttemptTimeoutError` once `timeoutMs` elapses, regardless of whether
 * `run` ever settles. A non-positive or non-finite `timeoutMs` means no deadline.
 */
export function runWithAbortTimeout<T>(
  run: AbortableRun<T>,
  timeoutMs: number,
): Promise<T> {
  const controller = new AbortController();
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return run(controller.signal);
  }

  let timer: ReturnType<typeof setTimeout> | undefined;
  let timedOut = false;

  const deadline = new Promise<never>((_resolve, reject) => {
    timer = setTimeout(() => {
      timedOut = true;
      // Let the SDK tear the child down; it cancels, then SIGKILLs after 5s.
      controller.abort();
      reject(new ClaudeAttemptTimeoutError(timeoutMs));
    }, timeoutMs);
  });

  // A rejection arriving after we already reported the timeout (the SDK's own
  // AbortError, typically) would otherwise surface as an unhandled rejection.
  const attempt = run(controller.signal).catch((err) => {
    if (timedOut) throw new ClaudeAttemptTimeoutError(timeoutMs);
    throw err;
  });
  attempt.catch(() => {});

  return Promise.race([attempt, deadline]).finally(() => {
    if (timer !== undefined) clearTimeout(timer);
  });
}
