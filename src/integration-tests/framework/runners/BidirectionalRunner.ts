import { spawn } from "node:child_process";
import type { CliRunResult, ICliRunner } from "../ICliRunner";

export interface BidirectionalRunnerConfig {
  agentId: string;
  baseUrl: string;
  apiKey: string;
  projectRoot: string;
  timeoutMs?: number;
}

export interface BidirectionalStreamLine {
  type: string;
  subtype?: string;
  request_id?: string;
  request?: { subtype?: string };
  event?: Record<string, unknown>;
  result?: string;
  stop_reason?: string;
  message_type?: string;
  [key: string]: unknown;
}

/** Extended result with per-event counters for assertion convenience. */
export interface BidirectionalRunResult extends CliRunResult {
  success: boolean;
  timedOut: boolean;
  /** Number of control_request(can_use_tool) or approval_request_message events seen. */
  approvalCount: number;
  toolCallCount: number;
  toolReturnCount: number;
  endTurnStopReasons: number;
  elapsedMs: number;
  messages: BidirectionalStreamLine[];
}

/**
 * Strategy: --input-format stream-json --output-format stream-json.
 *
 * Sends the prompt via stdin after receiving system:init.
 * Auto-approves every tool request (behavior: allow).
 * Returns extended BidirectionalRunResult which satisfies CliRunResult.
 */
export class BidirectionalRunner implements ICliRunner {
  constructor(private readonly cfg: BidirectionalRunnerConfig) {}

  run(prompt: string): Promise<BidirectionalRunResult> {
    const {
      agentId,
      baseUrl,
      apiKey,
      projectRoot,
      timeoutMs = 95_000,
    } = this.cfg;
    const startTime = Date.now();

    return new Promise<BidirectionalRunResult>((resolve, reject) => {
      const proc = spawn(
        "bun",
        [
          "run",
          "dev",
          "--agent",
          agentId,
          "--new",
          "-p",
          "--input-format",
          "stream-json",
          "--output-format",
          "stream-json",
          "--memfs-startup",
          "skip",
        ],
        {
          cwd: projectRoot,
          env: {
            ...process.env,
            LETTA_CODE_AGENT_ROLE: "subagent",
            LETTA_BASE_URL: baseUrl,
            LETTA_API_KEY: apiKey,
            LETTA_DEBUG: "0",
          },
          stdio: ["pipe", "pipe", "pipe"],
        },
      );

      let stdout = "";
      let stderr = "";
      const messages: BidirectionalStreamLine[] = [];
      let buf = "";
      let initReceived = false;
      let promptSent = false;
      let approvalCount = 0;
      let toolCallCount = 0;
      let toolReturnCount = 0;
      let endTurnStopReasons = 0;
      let settled = false;
      let timedOut = false;

      const finish = (success: boolean, isTimeout = false) => {
        if (settled) return;
        settled = true;
        timedOut = isTimeout;
        clearTimeout(completionTimer);
        clearTimeout(safetyTimer);
        try {
          proc.stdin?.end();
          proc.kill();
        } catch {
          /* ignore */
        }
        resolve({
          stdout,
          stderr,
          exitCode: success ? 0 : 1,
          success,
          timedOut,
          approvalCount,
          toolCallCount,
          toolReturnCount,
          endTurnStopReasons,
          elapsedMs: Date.now() - startTime,
          messages,
        });
      };

      const completionTimer = setTimeout(() => finish(false, true), timeoutMs);
      const safetyTimer = setTimeout(
        () => finish(false, true),
        timeoutMs + 5_000,
      );

      const processLine = (line: string) => {
        const trimmed = line.trim();
        if (!trimmed) return;
        let msg: BidirectionalStreamLine;
        try {
          msg = JSON.parse(trimmed) as BidirectionalStreamLine;
        } catch {
          return;
        }
        messages.push(msg);

        if (msg.type === "system" && msg.subtype === "init" && !initReceived) {
          initReceived = true;
          if (!promptSent) {
            promptSent = true;
            proc.stdin?.write(
              `${JSON.stringify({ type: "user", message: { role: "user", content: prompt } })}\n`,
            );
          }
          return;
        }

        if (
          msg.type === "control_request" &&
          msg.request?.subtype === "can_use_tool"
        ) {
          approvalCount += 1;
          if (msg.request_id) {
            proc.stdin?.write(
              `${JSON.stringify({ type: "control_response", response: { request_id: msg.request_id, response: { behavior: "allow" } } })}\n`,
            );
          }
          return;
        }

        const evt = msg.event;
        if (msg.type === "stream_event" && evt && typeof evt === "object") {
          if (evt.message_type === "approval_request_message")
            approvalCount += 1;
          if (evt.message_type === "tool_call_message") toolCallCount += 1;
          if (evt.message_type === "tool_return_message") toolReturnCount += 1;
          if (
            evt.message_type === "stop_reason" &&
            evt.stop_reason === "end_turn"
          )
            endTurnStopReasons += 1;
        }

        if (msg.type === "message" && typeof msg.message_type === "string") {
          if (msg.message_type === "tool_call_message") toolCallCount += 1;
          if (msg.message_type === "tool_return_message") toolReturnCount += 1;
          if (
            msg.message_type === "stop_reason" &&
            msg.stop_reason === "end_turn"
          )
            endTurnStopReasons += 1;
        }

        if (msg.type === "result") {
          finish(msg.subtype === "success");
          return;
        }
        if (msg.type === "error") {
          finish(false);
        }
      };

      proc.stdout?.on("data", (chunk: Buffer) => {
        const text = chunk.toString();
        stdout += text;
        buf += text;
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) processLine(line);
      });

      proc.stderr?.on("data", (c: Buffer) => {
        stderr += c.toString();
      });
      proc.on("close", () => {
        if (buf.trim()) processLine(buf);
        finish(false);
      });
      proc.on("error", (err) => {
        if (!settled) reject(err);
      });
    });
  }
}
