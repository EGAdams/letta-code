import { spawn } from "node:child_process";
import type { CliRunResult, ICliRunner } from "../ICliRunner";

export interface JsonOutputRunnerConfig {
  agentId: string;
  baseUrl: string;
  apiKey: string;
  projectRoot: string;
  conversation?: string;
  timeoutMs?: number;
  retryOnTimeouts?: number;
}

/**
 * Strategy: --output-format json.
 * Waits for the process to exit; retries on timeout up to retryOnTimeouts times.
 */
export class JsonOutputRunner implements ICliRunner {
  constructor(private readonly cfg: JsonOutputRunnerConfig) {}

  async run(prompt: string): Promise<CliRunResult> {
    const {
      agentId,
      baseUrl,
      apiKey,
      projectRoot,
      conversation = "default",
      timeoutMs = 300_000,
      retryOnTimeouts = 1,
    } = this.cfg;

    const runOnce = () =>
      new Promise<CliRunResult>((resolve, reject) => {
        const proc = spawn(
          "bun",
          [
            "run",
            "dev",
            "--agent",
            agentId,
            "--conversation",
            conversation,
            "-p",
            prompt,
            "--output-format",
            "json",
          ],
          {
            cwd: projectRoot,
            env: {
              ...process.env,
              LETTA_CODE_AGENT_ROLE: "subagent",
              LETTA_BASE_URL: baseUrl,
              LETTA_API_KEY: apiKey,
            },
          },
        );

        let stdout = "";
        let stderr = "";
        let settled = false;

        const timer = setTimeout(() => {
          if (settled) return;
          settled = true;
          proc.kill();
          reject(
            new Error(
              `JsonOutputRunner timed out after ${timeoutMs}ms.\nSTDOUT:\n${stdout}\nSTDERR:\n${stderr}`,
            ),
          );
        }, timeoutMs);

        proc.stdout?.on("data", (c: Buffer) => {
          stdout += c.toString();
        });
        proc.stderr?.on("data", (c: Buffer) => {
          stderr += c.toString();
        });
        proc.on("close", (code) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          resolve({ stdout, stderr, exitCode: code });
        });
        proc.on("error", (err) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          reject(err);
        });
      });

    let attempt = 0;
    while (true) {
      try {
        return await runOnce();
      } catch (err) {
        const isTimeout =
          err instanceof Error && err.message.includes("timed out after");
        if (!isTimeout || attempt >= retryOnTimeouts) throw err;
        attempt += 1;
      }
    }
  }
}
