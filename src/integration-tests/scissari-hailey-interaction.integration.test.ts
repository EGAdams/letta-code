import { beforeEach, describe, expect, test } from "bun:test";
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { getClient } from "../agent/client";
import { RemoteLogger } from "../logger/RemoteLogger";
import { settingsManager } from "../settings-manager";
import { resetAllLoggers } from "./logger-helpers";

const SCISSARI_AGENT_ID = "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa";
const DEFAULT_BASE_URL = "http://100.80.49.10:8283";
const TEST_API_KEY = "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8";
const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const LOGGER_ID = "ScissariHaileyInteraction_2026";

type JsonObject = Record<string, unknown>;

function parseJsonLines(stdout: string): JsonObject[] {
  return stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as JsonObject);
}

function extractRunIds(events: JsonObject[]): string[] {
  const ids = new Set<string>();
  for (const event of events) {
    const streamEvent = event.event;
    if (
      event.type === "stream_event" &&
      streamEvent &&
      typeof streamEvent === "object" &&
      "run_id" in streamEvent &&
      typeof streamEvent.run_id === "string"
    ) {
      ids.add(streamEvent.run_id);
    }
  }
  return [...ids];
}

function extractToolReturnEvents(events: JsonObject[]): JsonObject[] {
  return events.filter((event) => {
    const streamEvent = event.event;
    return (
      event.type === "stream_event" &&
      streamEvent &&
      typeof streamEvent === "object" &&
      streamEvent.message_type === "tool_return_message"
    );
  });
}

function messageContentText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (
          part &&
          typeof part === "object" &&
          "text" in part &&
          typeof part.text === "string"
        ) {
          return part.text;
        }
        return JSON.stringify(part);
      })
      .join("");
  }
  return content === undefined ? "" : JSON.stringify(content);
}

async function runScissariPrompt(
  prompt: string,
): Promise<{ stdout: string; stderr: string; exitCode: number | null }> {
  return new Promise((resolve, reject) => {
    const proc = spawn(
      "bun",
      [
        "run",
        "dev",
        "--agent",
        SCISSARI_AGENT_ID,
        "--new",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--include-partial-messages",
        "--memfs-startup",
        "skip",
        "--yolo",
      ],
      {
        cwd: projectRoot,
        env: {
          ...process.env,
          LETTA_CODE_AGENT_ROLE: "subagent",
          LETTA_BASE_URL: process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL,
          LETTA_API_KEY: process.env.LETTA_API_KEY ?? TEST_API_KEY,
        },
      },
    );

    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(() => {
      proc.kill();
      reject(
        new Error(
          `Timed out waiting for Scissari/Hailey interaction.\nSTDOUT:\n${stdout}\nSTDERR:\n${stderr}`,
        ),
      );
    }, 150000);

    proc.stdout?.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    proc.stderr?.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    proc.on("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    proc.on("close", (exitCode) => {
      clearTimeout(timeout);
      resolve({ stdout, stderr, exitCode });
    });
  });
}

describe("Scissari Hailey interaction integration", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" ? test : test.skip;

  maybeTest(
    "Scissari can ask Hailey and return a final user-facing answer",
    async () => {
      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs("Scissari Hailey interaction test run started.");
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[scissari-hailey] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[scissari-hailey] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch (err) {
          console.warn(
            `[scissari-hailey] log failed: ${err instanceof Error ? err.message : String(err)}`,
          );
        }
      };

      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      try {
        const token = `SCISSARI_HAILEY_INTERACTION_${Date.now()}`;
        const result = await runScissariPrompt(
          `Please ask Hailey how the finance report is going and what we are working on specifically, then summarize her answer for me. Include diagnostic token ${token} in your final answer.`,
        );

        await log(`CLI exit code: ${result.exitCode}`);
        expect(result.exitCode).toBe(0);

        const events = parseJsonLines(result.stdout);
        const finalResult = events.find((event) => event.type === "result");
        const finalText = String(finalResult?.result ?? "");
        await log(`final result preview: ${finalText.slice(0, 300)}`);

        expect(finalResult?.subtype).toBe("success");
        expect(finalText).toContain(token);
        expect(finalText).toContain("Hailey");
        expect(finalText).not.toContain("no assistant reply was returned");
        await log("PASS: Scissari returned Hailey's answer to the user");
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      }
    },
    { timeout: 180000 },
  );

  maybeTest(
    "Scissari stream includes a successful synthetic tool return for Hailey",
    async () => {
      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs(
          "Scissari Hailey tool-return interaction test run started.",
        );
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[scissari-hailey] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      const log = async (message: string) => {
        console.log(`[scissari-hailey] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch (err) {
          console.warn(
            `[scissari-hailey] log failed: ${err instanceof Error ? err.message : String(err)}`,
          );
        }
      };

      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      try {
        const token = `SCISSARI_HAILEY_TOOLRETURN_${Date.now()}`;
        const result = await runScissariPrompt(
          `Ask Hailey for a concise finance report status update and include diagnostic token ${token} in the final answer.`,
        );

        await log(`CLI exit code: ${result.exitCode}`);
        expect(result.exitCode).toBe(0);

        const events = parseJsonLines(result.stdout);
        const toolReturns = extractToolReturnEvents(events);
        const successfulToolReturn = toolReturns.find((event) => {
          const streamEvent = event.event as JsonObject;
          return (
            streamEvent.status === "success" &&
            String(streamEvent.tool_return ?? "").includes("Hailey replied:")
          );
        });

        if (!successfulToolReturn) {
          throw new Error(
            `No successful Hailey tool_return_message found. tool_returns=${JSON.stringify(toolReturns).slice(0, 1000)}`,
          );
        }

        const runIds = extractRunIds(events);
        expect(runIds.length).toBeGreaterThan(0);
        await log(`run_ids: ${runIds.join(",")}`);

        const client = await getClient();
        const persistedContextSeen = [];
        for (const runId of runIds) {
          const page = await client.runs.messages.list(runId, { limit: 50 });
          const messages = page.getPaginatedItems();
          const matched = messages.some((message) =>
            messageContentText(
              (message as unknown as Record<string, unknown>).content,
            ).includes("Hailey replied:"),
          );
          if (matched) persistedContextSeen.push(runId);
        }

        expect(persistedContextSeen.length).toBeGreaterThan(0);
        await log(
          `PASS: successful tool_return_message seen in stream and persisted context on runs ${persistedContextSeen.join(",")}`,
        );
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      }
    },
    { timeout: 180000 },
  );
});
