import { describe, expect, test } from "bun:test";
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { RemoteLogger } from "../logger/RemoteLogger";

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
        const proc = spawn("bun", ["run", "dev", ...args], {
          cwd: projectRoot,
          // Mark as subagent to prevent polluting user's LRU settings
          env: { ...process.env, LETTA_CODE_AGENT_ROLE: "subagent" },
        });

        let stdout = "";
        let stderr = "";
        let settled = false;

        const timeout = setTimeout(() => {
          if (settled) return;
          settled = true;
          proc.kill();
          reject(
            new Error(
              `Timed out after ${timeoutMs}ms.\nSTDOUT:\n${stdout}\nSTDERR:\n${stderr}`,
            ),
          );
        }, timeoutMs);

        proc.stdout?.on("data", (data) => {
          stdout += data.toString();
        });
        proc.stderr?.on("data", (data) => {
          stderr += data.toString();
        });

        proc.on("close", (code) => {
          if (settled) return;
          settled = true;
          clearTimeout(timeout);
          resolve({ stdout, stderr, exitCode: code });
        });

        proc.on("error", (error) => {
          if (settled) return;
          settled = true;
          clearTimeout(timeout);
          reject(error);
        });
      },
    );

  let attempt = 0;
  while (true) {
    try {
      return await runOnce();
    } catch (error) {
      const isTimeoutError =
        error instanceof Error && error.message.includes("Timed out after");
      if (!isTimeoutError || attempt >= retryOnTimeouts) {
        throw error;
      }
      attempt += 1;
      console.warn(
        `[scissari-test] retrying after timeout (${attempt}/${retryOnTimeouts})`,
      );
    }
  }
}

describe("Scissari agent integration", () => {
  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" ? test : test.skip;

  maybeTest(
    "letta-code can send a prompt to Scissari by agent ID",
    async () => {
      const logger = new RemoteLogger(
        `ScissariTest_${Math.floor(Date.now() / 1000)}`,
      );
      await logger.init();
      await logger.log(
        "Test started: letta-code can send a prompt to Scissari by agent ID",
      );
      await logger.log(`Agent ID: ${SCISSARI_AGENT_ID}`);
      await logger.log(`Prompt: ${SCISSARI_PROMPT}`);

      await logger.log(
        "Invoking runCli with --agent, --conversation, -p, --output-format json",
      );
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
        await logger.log(`CLI exited with code ${result.exitCode}`);
      } catch (err) {
        await logger.log(
          `CLI threw: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      }

      if (result.exitCode !== 0) {
        await logger.log(
          `FAIL: exit code ${result.exitCode}. STDERR: ${result.stderr.slice(0, 500)}`,
        );
        throw new Error(
          `Expected exit code 0, got ${result.exitCode}.\nSTDERR:\n${result.stderr}\nSTDOUT:\n${result.stdout}`,
        );
      }
      await logger.log("exit code check passed");

      let output: Record<string, unknown>;
      try {
        output = extractJsonObject(result.stdout);
        await logger.log(
          `JSON extracted. Keys: ${Object.keys(output).join(", ")}`,
        );
      } catch (err) {
        await logger.log(
          `JSON extraction failed: ${err instanceof Error ? err.message : String(err)}`,
        );
        throw err;
      }

      const agentIdMatch = output.agent_id === SCISSARI_AGENT_ID;
      await logger.log(
        `agent_id check: ${agentIdMatch ? "PASS" : "FAIL"} (got ${String(output.agent_id)})`,
      );
      expect(output.agent_id).toBe(SCISSARI_AGENT_ID);

      const resultType = typeof output.result;
      await logger.log(
        `result type check: ${resultType === "string" ? "PASS" : "FAIL"} (got ${resultType})`,
      );
      expect(resultType).toBe("string");

      const resultStr = String(output.result);
      const tokenFound = resultStr.includes("SCISSARI_TEST_OK");
      await logger.log(
        `SCISSARI_TEST_OK token check: ${tokenFound ? "PASS" : "FAIL"}`,
      );
      if (!tokenFound) {
        await logger.log(`result value: ${resultStr.slice(0, 500)}`);
      }
      expect(resultStr).toContain("SCISSARI_TEST_OK");

      await logger.log("All assertions passed. Test complete.");
    },
    { timeout: 190000 },
  );
});
