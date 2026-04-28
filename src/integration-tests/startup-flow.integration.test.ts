import { beforeEach, describe, expect, test } from "bun:test";
import { spawn } from "node:child_process";
import { RemoteLogger } from "../logger/RemoteLogger";
import { resetAllLoggers } from "./logger-helpers";

const TEST_TIMEOUT_MS = 30000;

const normalizeLoggerMessage = (message: string): string => {
  if (message.includes("ERROR")) return message;
  if (/\bFAIL(?:ED)?\b/.test(message)) return `ERROR: `;
  if (/\bPASS(?:ED)?\b/.test(message) || /test complete|test finished/i.test(message)) {
    return message.includes("finished") ? message : ` finished`;
  }
  return message;
};
const testWithTimeout = (name: string, fn: () => Promise<void> | void) =>
  test(name, fn, TEST_TIMEOUT_MS);

/**
 * Startup flow integration tests.
 *
 * These spawn the real CLI and require LETTA_API_KEY to be set.
 * They are executed in CI only for push to main / trusted PRs (non-forks).
 */

const projectRoot = process.cwd();

async function runCli(
  args: string[],
  options: {
    timeoutMs?: number;
    expectExit?: number;
    retryOnTimeouts?: number;
  } = {},
): Promise<{ stdout: string; stderr: string; exitCode: number | null }> {
  const { timeoutMs = 30000, expectExit, retryOnTimeouts = 1 } = options;

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

        proc.stdout?.on("data", (data) => {
          stdout += data.toString();
        });

        proc.stderr?.on("data", (data) => {
          stderr += data.toString();
        });

        const timeout = setTimeout(() => {
          proc.kill();
          reject(
            new Error(
              `Timeout after ${timeoutMs}ms. stdout: ${stdout}, stderr: ${stderr}`,
            ),
          );
        }, timeoutMs);

        proc.on("close", (code) => {
          clearTimeout(timeout);
          if (expectExit !== undefined && code !== expectExit) {
            reject(
              new Error(
                `Expected exit code ${expectExit}, got ${code}. stdout: ${stdout}, stderr: ${stderr}`,
              ),
            );
          } else {
            resolve({ stdout, stderr, exitCode: code });
          }
        });

        proc.on("error", (err) => {
          clearTimeout(timeout);
          reject(err);
        });
      },
    );

  let attempt = 0;
  while (true) {
    try {
      return await runOnce();
    } catch (error) {
      const isTimeoutError =
        error instanceof Error && error.message.includes("Timeout after");
      if (!isTimeoutError || attempt >= retryOnTimeouts) {
        throw error;
      }
      attempt += 1;
      console.warn(
        `[startup-flow] retrying after timeout (${attempt}/${retryOnTimeouts}) args=${args.join(" ")}`,
      );
    }
  }
}

// ============================================================================
// Invalid Input Tests (require API calls but fail fast)
// ============================================================================

describe("Startup Flow - Invalid Inputs", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  testWithTimeout(
    "--agent with nonexistent ID shows error",
    async () => {
      const logger = new RemoteLogger("StartupFlow_AgentNotFound_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(`[startup-flow:AgentNotFound] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
      }
      const log = async (message: string) => {
        console.log(`[startup-flow:AgentNotFound] ${message}`);
        if (loggerReady) {
          try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
            console.error(`[startup-flow:AgentNotFound] log failed: ${err instanceof Error ? err.message : String(err)}`);
          }
        }
      };

      await log("Test started: --agent with nonexistent ID shows error");
      await log("Args: --agent agent-definitely-does-not-exist-12345 -p test");
      const result = await runCli(
        ["--agent", "agent-definitely-does-not-exist-12345", "-p", "test"],
        { expectExit: 1, timeoutMs: 60000 },
      );
      await log(`exitCode=${result.exitCode} stderr contains 'not found': ${result.stderr.includes("not found")}`);
      expect(result.stderr).toContain("not found");
      await log("stderr contains 'not found': PASS — test complete");
    },
    { timeout: 70000 },
  );

  testWithTimeout(
    "--conversation with nonexistent ID shows error",
    async () => {
      const logger = new RemoteLogger("StartupFlow_ConvNotFound_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(`[startup-flow:ConvNotFound] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
      }
      const log = async (message: string) => {
        console.log(`[startup-flow:ConvNotFound] ${message}`);
        if (loggerReady) {
          try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
            console.error(`[startup-flow:ConvNotFound] log failed: ${err instanceof Error ? err.message : String(err)}`);
          }
        }
      };

      await log("Test started: --conversation with nonexistent ID shows error");
      await log("Args: --conversation conversation-definitely-does-not-exist-12345 -p test");
      const result = await runCli(
        [
          "--conversation",
          "conversation-definitely-does-not-exist-12345",
          "-p",
          "test",
        ],
        { expectExit: 1, timeoutMs: 60000 },
      );
      await log(`exitCode=${result.exitCode} stderr contains 'not found': ${result.stderr.includes("not found")}`);
      expect(result.stderr).toContain("not found");
      await log("stderr contains 'not found': PASS — test complete");
    },
    { timeout: 70000 },
  );

  testWithTimeout("--import with nonexistent file shows error", async () => {
    const logger = new RemoteLogger("StartupFlow_ImportNotFound_2026");
    let loggerReady = false;
    try {
      await logger.init();
      loggerReady = true;
    } catch (err) {
      console.warn(`[startup-flow:ImportNotFound] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
    }
    const log = async (message: string) => {
      console.log(`[startup-flow:ImportNotFound] ${message}`);
      if (loggerReady) {
        try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
          console.error(`[startup-flow:ImportNotFound] log failed: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    };

    await log("Test started: --import with nonexistent file shows error");
    await log("Args: --import /nonexistent/path/agent.af -p test");
    const result = await runCli(
      ["--import", "/nonexistent/path/agent.af", "-p", "test"],
      { expectExit: 1 },
    );
    await log(`exitCode=${result.exitCode} stderr contains 'not found': ${result.stderr.includes("not found")}`);
    expect(result.stderr).toContain("not found");
    await log("stderr contains 'not found': PASS — test complete");
  });
});

// ============================================================================
// Integration Tests (require API access, create real agents)
// ============================================================================

describe("Startup Flow - Integration", () => {
  let testAgentId: string | null = null;

  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  testWithTimeout(
    "--new-agent creates agent and responds",
    async () => {
      const logger = new RemoteLogger("StartupFlow_NewAgent_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(`[startup-flow:NewAgent] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
      }
      const log = async (message: string) => {
        console.log(`[startup-flow:NewAgent] ${message}`);
        if (loggerReady) {
          try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
            console.error(`[startup-flow:NewAgent] log failed: ${err instanceof Error ? err.message : String(err)}`);
          }
        }
      };

      await log("Test started: --new-agent creates agent and responds");
      await log("Args: --new-agent -m gpt-5.4-mini-plus-pro-medium -p 'Say OK and nothing else' --output-format json");
      const result = await runCli(
        [
          "--new-agent",
          "-m",
          "gpt-5.4-mini-plus-pro-medium",
          "-p",
          "Say OK and nothing else",
          "--output-format",
          "json",
        ],
        { timeoutMs: 180000 },
      );
      await log(`exitCode=${result.exitCode}`);

      expect(result.exitCode).toBe(0);
      const jsonStart = result.stdout.indexOf("{");
      const output = JSON.parse(result.stdout.slice(jsonStart));
      expect(output.agent_id).toBeDefined();
      expect(output.result).toBeDefined();

      testAgentId = output.agent_id;
      await log(`agent created: agent_id=${testAgentId} — test complete`);
    },
    { timeout: 190000 },
  );

  testWithTimeout(
    "--agent with valid ID uses that agent",
    async () => {
      const logger = new RemoteLogger("StartupFlow_ValidAgent_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(`[startup-flow:ValidAgent] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
      }
      const log = async (message: string) => {
        console.log(`[startup-flow:ValidAgent] ${message}`);
        if (loggerReady) {
          try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
            console.error(`[startup-flow:ValidAgent] log failed: ${err instanceof Error ? err.message : String(err)}`);
          }
        }
      };

      await log("Test started: --agent with valid ID uses that agent");
      if (!testAgentId) {
        await log("SKIP: no test agent available from previous test");
        console.log("Skipping: no test agent available");
        return;
      }
      await log(`Using agent_id=${testAgentId}`);

      const result = await runCli(
        [
          "--agent",
          testAgentId,
          "-m",
          "gpt-5.4-mini-plus-pro-medium",
          "-p",
          "Say OK",
          "--output-format",
          "json",
        ],
        { timeoutMs: 180000 },
      );
      await log(`exitCode=${result.exitCode}`);

      expect(result.exitCode).toBe(0);
      const jsonStart = result.stdout.indexOf("{");
      const output = JSON.parse(result.stdout.slice(jsonStart));
      expect(output.agent_id).toBe(testAgentId);
      await log(`output.agent_id=${output.agent_id} matches testAgentId: PASS — test complete`);
    },
    { timeout: 190000 },
  );

  testWithTimeout(
    "--conversation with valid ID derives agent and uses conversation",
    async () => {
      const logger = new RemoteLogger("StartupFlow_ValidConv_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(`[startup-flow:ValidConv] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
      }
      const log = async (message: string) => {
        console.log(`[startup-flow:ValidConv] ${message}`);
        if (loggerReady) {
          try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
            console.error(`[startup-flow:ValidConv] log failed: ${err instanceof Error ? err.message : String(err)}`);
          }
        }
      };

      await log("Test started: --conversation with valid ID derives agent and uses conversation");
      if (!testAgentId) {
        await log("SKIP: no test agent available from previous test");
        console.log("Skipping: no test agent available");
        return;
      }
      await log(`Using agent_id=${testAgentId}`);

      await log("Phase 1: creating real conversation with --new");
      const createResult = await runCli(
        [
          "--agent",
          testAgentId,
          "--new",
          "-m",
          "gpt-5.4-mini-plus-pro-medium",
          "-p",
          "Say CREATED",
          "--output-format",
          "json",
        ],
        { timeoutMs: 180000 },
      );
      expect(createResult.exitCode).toBe(0);
      const createJsonStart = createResult.stdout.indexOf("{");
      const createOutput = JSON.parse(
        createResult.stdout.slice(createJsonStart),
      );
      const realConversationId = createOutput.conversation_id;
      expect(realConversationId).toBeDefined();
      expect(realConversationId).not.toBe("default");
      await log(`Phase 1 complete: conversation_id=${realConversationId}`);

      await log("Phase 2: using --conversation with real conversation ID");
      const result = await runCli(
        [
          "--conversation",
          realConversationId,
          "-m",
          "gpt-5.4-mini-plus-pro-medium",
          "-p",
          "Say OK",
          "--output-format",
          "json",
        ],
        { timeoutMs: 180000 },
      );
      await log(`exitCode=${result.exitCode}`);

      expect(result.exitCode).toBe(0);
      const jsonStart = result.stdout.indexOf("{");
      const output = JSON.parse(result.stdout.slice(jsonStart));
      expect(output.agent_id).toBe(testAgentId);
      expect(output.conversation_id).toBe(realConversationId);
      await log(`agent_id=${output.agent_id} conversation_id=${output.conversation_id} — test complete`);
    },
    { timeout: 180000 },
  );

  testWithTimeout(
    "--agent + --conversation default succeeds and stays on default route",
    async () => {
      const logger = new RemoteLogger("StartupFlow_DefaultConv_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(`[startup-flow:DefaultConv] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
      }
      const log = async (message: string) => {
        console.log(`[startup-flow:DefaultConv] ${message}`);
        if (loggerReady) {
          try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
            console.error(`[startup-flow:DefaultConv] log failed: ${err instanceof Error ? err.message : String(err)}`);
          }
        }
      };

      await log("Test started: --agent + --conversation default succeeds and stays on default route");
      let agentIdForTest = testAgentId;
      if (!agentIdForTest) {
        await log("No test agent from prior test — bootstrapping new agent");
        const bootstrapResult = await runCli(
          [
            "--new-agent",
            "-m",
            "gpt-5.4-mini-plus-pro-medium",
            "-p",
            "Say OK",
            "--output-format",
            "json",
          ],
          { timeoutMs: 180000 },
        );
        expect(bootstrapResult.exitCode).toBe(0);
        const bootstrapJsonStart = bootstrapResult.stdout.indexOf("{");
        const bootstrapOutput = JSON.parse(
          bootstrapResult.stdout.slice(bootstrapJsonStart),
        );
        agentIdForTest = bootstrapOutput.agent_id as string;
        testAgentId = agentIdForTest;
        await log(`Bootstrap agent created: agent_id=${agentIdForTest}`);
      }

      await log(`Using agent_id=${agentIdForTest} with --conversation default`);
      const result = await runCli(
        [
          "--agent",
          agentIdForTest,
          "--conversation",
          "default",
          "-m",
          "gpt-5.4-mini-plus-pro-medium",
          "-p",
          "Say OK",
          "--output-format",
          "json",
        ],
        { timeoutMs: 180000 },
      );
      await log(`exitCode=${result.exitCode}`);

      expect(result.exitCode).toBe(0);
      const jsonStart = result.stdout.indexOf("{");
      const output = JSON.parse(result.stdout.slice(jsonStart));
      expect(output.agent_id).toBe(agentIdForTest);
      expect(output.conversation_id).toBe("default");
      await log(`agent_id=${output.agent_id} conversation_id=${output.conversation_id} — test complete`);
    },
    { timeout: 190000 },
  );

  testWithTimeout(
    "--new-agent with --init-blocks none creates minimal agent",
    async () => {
      const logger = new RemoteLogger("StartupFlow_InitBlocksNone_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(`[startup-flow:InitBlocksNone] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`);
      }
      const log = async (message: string) => {
        console.log(`[startup-flow:InitBlocksNone] ${message}`);
        if (loggerReady) {
          try { await logger.log(normalizeLoggerMessage(message)); } catch (err) {
            console.error(`[startup-flow:InitBlocksNone] log failed: ${err instanceof Error ? err.message : String(err)}`);
          }
        }
      };

      await log("Test started: --new-agent with --init-blocks none creates minimal agent");
      await log("Args: --new-agent --init-blocks none -m gpt-5.4-mini-plus-pro-medium -p 'Say OK' --output-format json");
      const result = await runCli(
        [
          "--new-agent",
          "--init-blocks",
          "none",
          "-m",
          "gpt-5.4-mini-plus-pro-medium",
          "-p",
          "Say OK",
          "--output-format",
          "json",
        ],
        { timeoutMs: 180000 },
      );
      await log(`exitCode=${result.exitCode}`);

      expect(result.exitCode).toBe(0);
      const jsonStart = result.stdout.indexOf("{");
      const output = JSON.parse(result.stdout.slice(jsonStart));
      expect(output.agent_id).toBeDefined();
      await log(`minimal agent created: agent_id=${output.agent_id} — test complete`);
    },
    { timeout: 190000 },
  );
});
