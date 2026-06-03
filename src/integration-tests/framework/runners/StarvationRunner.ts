import { spawn } from "node:child_process";
import type { CliRunResult, ICliRunner } from "../ICliRunner";

export interface StarvationRunnerConfig {
  agentId: string;
  baseUrl: string;
  apiKey: string;
  projectRoot: string;
  starvationTimeoutMs?: number;
  maxTotalTimeMs?: number;
  newConversation?: boolean;
  includePartialMessages?: boolean;
  memfsStartup?: "skip" | "run";
}

/** Extended result with starvation-detection metadata. */
export interface StarvationRunResult extends CliRunResult {
  /** True if no output arrived for starvationTimeoutMs while the process was still running. */
  starved: boolean;
  /** True if the process exceeded maxTotalTimeMs. */
  timedOut: boolean;
  /** ms since last output (or since starvation was detected). */
  starvationMs: number;
  /** False if the process exited before producing any output at all. */
  hasOutput: boolean;
}

/**
 * Strategy: stream-json output with output-starvation detection.
 * Used for planning-mode and inactivity tests where the agent may go silent
 * for extended periods. Kills the process when no output arrives for
 * starvationTimeoutMs, and fails if that threshold is exceeded.
 */
export class StarvationRunner implements ICliRunner {
  constructor(private readonly cfg: StarvationRunnerConfig) {}

  run(prompt: string): Promise<StarvationRunResult> {
    const {
      agentId,
      baseUrl,
      apiKey,
      projectRoot,
      starvationTimeoutMs = 45_000,
      maxTotalTimeMs = 120_000,
      newConversation = false,
      includePartialMessages = true,
      memfsStartup = "skip",
    } = this.cfg;

    return new Promise((resolve, reject) => {
      const args = ["run", "dev", "--agent", agentId];
      if (newConversation) args.push("--new");
      args.push("-p", prompt, "--output-format", "stream-json");
      if (includePartialMessages) args.push("--include-partial-messages");
      if (memfsStartup) args.push("--memfs-startup", memfsStartup);

      const proc = spawn("bun", args, {
        cwd: projectRoot,
        env: {
          ...process.env,
          LETTA_CODE_AGENT_ROLE: "subagent",
          LETTA_BASE_URL: baseUrl,
          LETTA_API_KEY: apiKey,
        },
      });

      let stdout = "";
      let stderr = "";
      let lastOutputTime = Date.now();
      let starved = false;
      let timedOut = false;
      let starvationDetectedAt = 0;
      let hasOutput = false;
      let processClosed = false;

      const starvationPoll = setInterval(() => {
        if (!hasOutput || starved) return;
        if (Date.now() - lastOutputTime > starvationTimeoutMs) {
          starved = true;
          starvationDetectedAt = Date.now();
          proc.kill();
        }
      }, 1_000);

      const totalTimer = setTimeout(() => {
        if (!processClosed) {
          timedOut = true;
          proc.kill();
        }
      }, maxTotalTimeMs);

      proc.stdout?.on("data", (c: Buffer) => {
        lastOutputTime = Date.now();
        stdout += c.toString();
        hasOutput = true;
      });
      proc.stderr?.on("data", (c: Buffer) => {
        lastOutputTime = Date.now();
        stderr += c.toString();
      });

      proc.on("error", (err) => {
        clearInterval(starvationPoll);
        clearTimeout(totalTimer);
        reject(err);
      });

      proc.on("close", (code, signal) => {
        processClosed = true;
        clearInterval(starvationPoll);
        clearTimeout(totalTimer);
        const starvationMs = starved
          ? Date.now() - starvationDetectedAt
          : Date.now() - lastOutputTime;
        const exitCode = code !== null ? code : signal ? 128 + 15 : -1;
        resolve({
          stdout,
          stderr,
          exitCode,
          starved,
          timedOut,
          starvationMs,
          hasOutput,
        });
      });
    });
  }
}
