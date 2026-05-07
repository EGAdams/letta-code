import { beforeEach, describe, expect, test } from "bun:test";
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { RemoteLogger } from "../logger/RemoteLogger";
import { resetAllLoggers } from "./logger-helpers";

const SCISSARI_AGENT_ID = "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa";
const SCISSARI_PROMPT =
  "This is an automated integration test. Reply with a short greeting and include the exact token SCISSARI_TEST_OK.";
const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

function extractJsonObject(stdout: string): Record<string, unknown> {
  const start = stdout.indexOf("{");
  if (start < 0) {
    throw new Error(`No JSON object found in stdout:\n${stdout}`);
  }
  return JSON.parse(stdout.slice(start)) as Record<string, unknown>;
}

async function runCli(
  args: string[],
  timeoutMs = 300000,
  retryOnTimeouts = 1,
): Promise<{ stdout: string; stderr: string; exitCode: number | null }> {
  const runOnce = () =>
    new Promise<{ stdout: string; stderr: string; exitCode: number | null }>(
      (resolve, reject) => {
        console.log(
          `[scissari-test:runCli] Starting process with args: ${args.join(" ")}`,
        );

        const procEnv = { ...process.env };
        procEnv.LETTA_CODE_AGENT_ROLE = "subagent";
        // From Windows 11 WSL → Windows 10 Docker: 100.80.49.10:8283
        // From Windows 10 itself: localhost:8283
        // Override by setting LETTA_BASE_URL in the environment before running the test
        procEnv.LETTA_BASE_URL =
          process.env.LETTA_BASE_URL ?? "http://100.80.49.10:8283";
        procEnv.LETTA_API_KEY = "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8";

        console.log(
          `[scissari-test:runCli] Spawning 'bun run dev' in ${projectRoot}`,
        );
        const proc = spawn("bun", ["run", "dev", ...args], {
          cwd: projectRoot,
          env: procEnv,
        });

        console.log(
          `[scissari-test:runCli] Process spawned with PID: ${proc.pid}`,
        );

        let stdout = "";
        let stderr = "";
        let settled = false;
        let lastDataTime = Date.now();
        const startTime = Date.now();

        const heartbeat = setInterval(() => {
          if (settled) return;
          const elapsedSec = Math.round((Date.now() - startTime) / 1000);
          const silenceSec = Math.round((Date.now() - lastDataTime) / 1000);
          console.log(
            `[scissari-test:runCli] HEARTBEAT — still waiting at ${elapsedSec}s elapsed, ` +
              `${silenceSec}s since last data. stdout=${stdout.length}B stderr=${stderr.length}B`,
          );
        }, 10000);

        const timeout = setTimeout(() => {
          if (settled) return;
          settled = true;
          clearInterval(heartbeat);
          console.error(
            `[scissari-test:runCli] TIMEOUT after ${timeoutMs}ms, killing process`,
          );
          proc.kill();
          reject(
            new Error(
              `Timed out after ${timeoutMs}ms.\nSTDOUT:\n${stdout}\nSTDERR:\n${stderr}`,
            ),
          );
        }, timeoutMs);

        proc.stdout?.on("data", (data) => {
          lastDataTime = Date.now();
          const chunk = data.toString();
          stdout += chunk;
          console.log(
            `[scissari-test:runCli] STDOUT chunk (${chunk.length} bytes):\n${chunk}`,
          );
        });

        proc.stderr?.on("data", (data) => {
          lastDataTime = Date.now();
          const chunk = data.toString();
          stderr += chunk;
          console.log(
            `[scissari-test:runCli] STDERR chunk (${chunk.length} bytes):\n${chunk}`,
          );
        });

        proc.on("close", (code) => {
          if (settled) return;
          settled = true;
          clearTimeout(timeout);
          clearInterval(heartbeat);
          console.log(
            `[scissari-test:runCli] Process closed with exit code: ${code}`,
          );
          console.log(
            `[scissari-test:runCli] Total stdout: ${stdout.length} bytes`,
          );
          console.log(
            `[scissari-test:runCli] Total stderr: ${stderr.length} bytes`,
          );
          resolve({ stdout, stderr, exitCode: code });
        });

        proc.on("error", (error) => {
          if (settled) return;
          settled = true;
          clearTimeout(timeout);
          clearInterval(heartbeat);
          console.error(
            `[scissari-test:runCli] Process error: ${error.message}`,
          );
          reject(error);
        });
      },
    );

  let attempt = 0;
  while (true) {
    try {
      console.log(
        `[scissari-test:runCli] Attempt ${attempt + 1}/${retryOnTimeouts + 1}`,
      );
      return await runOnce();
    } catch (error) {
      const isTimeoutError =
        error instanceof Error && error.message.includes("Timed out after");
      if (!isTimeoutError || attempt >= retryOnTimeouts) {
        console.error(
          `[scissari-test:runCli] Final error: ${error instanceof Error ? error.message : String(error)}`,
        );
        throw error;
      }
      attempt += 1;
      console.warn(
        `[scissari-test:runCli] Retrying after timeout (${attempt}/${retryOnTimeouts})`,
      );
    }
  }
}

beforeEach(async () => {
  await resetAllLoggers();
});

describe("Scissari agent integration", () => {
  const TEST_TIMEOUT_MS = 30000;

  const normalizeLoggerMessage = (message: string): string => {
    if (message.includes("ERROR")) return message;
    if (/\bFAIL(?:ED)?\b/.test(message)) return `ERROR: ${message}`;
    if (
      /\bPASS(?:ED)?\b/.test(message) ||
      /test complete|test finished/i.test(message)
    ) {
      return message.includes("finished") ? message : `${message} finished`;
    }
    return message;
  };

  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1"
      ? (
          name: string,
          fn: () => Promise<void> | void,
          opts?: { timeout?: number } | number,
        ) =>
          test(
            name,
            fn,
            typeof opts === "number"
              ? opts
              : (opts?.timeout ?? TEST_TIMEOUT_MS),
          )
      : (
          name: string,
          fn: () => Promise<void> | void,
          _opts?: { timeout?: number } | number,
        ) => test.skip(name, fn);

  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  maybeTest(
    "letta-code can send a prompt to Scissari by agent ID",
    async () => {
      console.log("[scissari-test] Test starting...");

      const loggerId = "ScissariTestLogger_2026";
      console.log(`[scissari-test] Creating RemoteLogger with ID: ${loggerId}`);

      const logger = new RemoteLogger(loggerId);
      const exitOnLoggerFailure = (context: string, err: unknown): never => {
        const detail = err instanceof Error ? err.message : String(err);
        console.error(`[scissari-test] ${context}: ${detail}`);
        process.exit(1);
      };

      try {
        console.log("[scissari-test] Initializing RemoteLogger...");
        await logger.init();
        await logger.clearLogs("Scissari test ready.");
        console.log("[scissari-test] RemoteLogger initialized successfully");
      } catch (err) {
        exitOnLoggerFailure("RemoteLogger init failed", err);
      }

      const log = async (message: string) => {
        const prefix = "[scissari-test-log]";
        console.log(`${prefix} ${message}`);
        try {
          await logger.log(normalizeLoggerMessage(message));
        } catch (err) {
          exitOnLoggerFailure("Failed to log", err);
        }
      };

      try {
        await log(
          "Test started: letta-code can send a prompt to Scissari by agent ID",
        );
        await log(`Agent ID: ${SCISSARI_AGENT_ID}`);
        await log(`Prompt: ${SCISSARI_PROMPT}`);

        await log(
          "Invoking runCli with --agent, --conversation, -p, --output-format json",
        );
        console.log("[scissari-test] Starting CLI invocation...");
        let result: { stdout: string; stderr: string; exitCode: number | null };
        try {
          result = await runCli([
            "--agent",
            SCISSARI_AGENT_ID,
            "--conversation",
            "default",
            "-p",
            SCISSARI_PROMPT,
            "--output-format",
            "json",
          ]);
          console.log(
            `[scissari-test] CLI returned with exit code: ${result.exitCode}`,
          );
          await log(`CLI exited with code ${result.exitCode}`);
        } catch (err) {
          await log(
            `CLI threw: ${err instanceof Error ? err.message : String(err)}`,
          );
          throw err;
        }

        if (result.exitCode !== 0) {
          await log(
            `FAIL: exit code ${result.exitCode}. STDERR: ${result.stderr.slice(0, 500)}`,
          );
          throw new Error(
            `Expected exit code 0, got ${result.exitCode}.\nSTDERR:\n${result.stderr}\nSTDOUT:\n${result.stdout}`,
          );
        }
        await log("exit code check passed");

        let output: Record<string, unknown>;
        try {
          console.log("[scissari-test] Parsing JSON output...");
          output = extractJsonObject(result.stdout);
          console.log(
            `[scissari-test] JSON parsed successfully. Keys: ${Object.keys(output).join(", ")}`,
          );
          await log(`JSON extracted. Keys: ${Object.keys(output).join(", ")}`);
        } catch (err) {
          console.error(
            `[scissari-test] JSON extraction failed: ${err instanceof Error ? err.message : String(err)}`,
          );
          await log(
            `JSON extraction failed: ${err instanceof Error ? err.message : String(err)}`,
          );
          throw err;
        }

        const agentIdMatch = output.agent_id === SCISSARI_AGENT_ID;
        console.log(
          `[scissari-test] agent_id check: ${agentIdMatch ? "PASS" : "FAIL"} (expected: ${SCISSARI_AGENT_ID}, got: ${String(output.agent_id)})`,
        );
        await log(
          `agent_id check: ${agentIdMatch ? "PASS" : "FAIL"} (got ${String(output.agent_id)})`,
        );
        expect(output.agent_id).toBe(SCISSARI_AGENT_ID);

        const resultType = typeof output.result;
        console.log(
          `[scissari-test] result type check: ${resultType === "string" ? "PASS" : "FAIL"} (got ${resultType})`,
        );
        await log(
          `result type check: ${resultType === "string" ? "PASS" : "FAIL"} (got ${resultType})`,
        );
        expect(resultType).toBe("string");

        const resultStr = String(output.result);
        const tokenFound = resultStr.includes("SCISSARI_TEST_OK");
        console.log(
          `[scissari-test] SCISSARI_TEST_OK token check: ${tokenFound ? "PASS" : "FAIL"}`,
        );
        await log(
          `SCISSARI_TEST_OK token check: ${tokenFound ? "PASS" : "FAIL"}`,
        );
        if (!tokenFound) {
          console.log(
            `[scissari-test] result value (first 500 chars): ${resultStr.slice(0, 500)}`,
          );
          await log(`result value: ${resultStr.slice(0, 500)}`);
        }
        expect(resultStr).toContain("SCISSARI_TEST_OK");

        console.log("[scissari-test] All assertions passed!");
        await log("All assertions passed. Test complete.");
      } finally {
        console.log("[scissari-test] Cleaning up...");
        console.log(
          "[scissari-test] Leaving logger record in place for viewer inspection",
        );
        console.log("[scissari-test] Test cleanup complete");
      }
    },
    { timeout: 190000 },
  );
});
