import { spawn } from "node:child_process";
import type { CliRunResult, ICliRunner } from "../ICliRunner";

export interface StreamJsonRunnerConfig {
  agentId: string;
  baseUrl: string;
  apiKey: string;
  projectRoot: string;
  newConversation?: boolean;
  yolo?: boolean;
  includePartialMessages?: boolean;
  memfsStartup?: "skip" | "run";
  timeoutMs?: number;
}

/**
 * Strategy: --output-format stream-json.
 * Resolves as soon as a {type:"result"} or {type:"error"} line arrives.
 */
export class StreamJsonRunner implements ICliRunner {
  constructor(private readonly cfg: StreamJsonRunnerConfig) {}

  run(prompt: string): Promise<CliRunResult> {
    const {
      agentId,
      baseUrl,
      apiKey,
      projectRoot,
      newConversation = true,
      yolo = false,
      includePartialMessages = true,
      memfsStartup = "skip",
      timeoutMs = 120_000,
    } = this.cfg;

    return new Promise((resolve, reject) => {
      const args = ["run", "dev", "--agent", agentId];
      if (newConversation) args.push("--new");
      args.push("-p", prompt, "--output-format", "stream-json");
      if (includePartialMessages) args.push("--include-partial-messages");
      if (memfsStartup) args.push("--memfs-startup", memfsStartup);
      if (yolo) args.push("--yolo");

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
      let buf = "";
      let settled = false;

      const finish = (exitCode: number | null) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        try {
          proc.kill();
        } catch {
          /* ignore */
        }
        resolve({ stdout, stderr, exitCode });
      };

      const timer = setTimeout(() => {
        if (settled) return;
        settled = true;
        proc.kill();
        reject(
          new Error(
            `StreamJsonRunner timed out after ${timeoutMs}ms.\nSTDOUT:\n${stdout}\nSTDERR:\n${stderr}`,
          ),
        );
      }, timeoutMs);

      proc.stdout?.on("data", (chunk: Buffer) => {
        const text = chunk.toString();
        stdout += text;
        buf += text;
        while (true) {
          const nl = buf.indexOf("\n");
          if (nl === -1) break;
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (!line) continue;
          try {
            const parsed = JSON.parse(line) as { type: string };
            if (parsed.type === "result") {
              finish(0);
              return;
            }
            if (parsed.type === "error") {
              finish(1);
              return;
            }
          } catch {
            /* keep buffering */
          }
        }
      });

      proc.stderr?.on("data", (chunk: Buffer) => {
        stderr += chunk.toString();
      });
      proc.on("close", (code) => finish(code));
      proc.on("error", (err) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        reject(err);
      });
    });
  }
}
