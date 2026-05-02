import { describe, expect, test } from "bun:test";
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { getClient } from "../agent/client";
import { settingsManager } from "../settings-manager";

const SCISSARI_AGENT_ID = "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa";
const DEFAULT_BASE_URL = "http://100.80.49.10:8283";
const TEST_API_KEY = "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8";
const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

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
          `Timed out waiting for Scissari prompt.\nSTDOUT:\n${stdout}\nSTDERR:\n${stderr}`,
        ),
      );
    }, 120000);

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

describe("Scissari message persistence integration", () => {
  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" ? test : test.skip;

  maybeTest(
    "streamed assistant response is persisted on the run",
    async () => {
      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      const token = `SCISSARI_PERSIST_${Date.now()}`;
      const result = await runScissariPrompt(
        `Reply with exactly ${token}. Do not use tools.`,
      );

      expect(result.exitCode).toBe(0);

      const events = parseJsonLines(result.stdout);
      const finalResult = events.find((event) => event.type === "result");
      expect(finalResult?.subtype).toBe("success");
      expect(String(finalResult?.result ?? "")).toContain(token);

      const runIds = extractRunIds(events);
      expect(runIds.length).toBeGreaterThan(0);

      const client = await getClient();
      const runId = runIds.at(-1) ?? "";
      const runMessages = await client.runs.messages.list(runId, {
        limit: 20,
      });
      const messages = runMessages.getPaginatedItems();
      const assistantMessages = messages.filter(
        (message) => message.message_type === "assistant_message",
      );
      const persistedAssistantHasToken = assistantMessages.some((message) =>
        messageContentText(
          (message as unknown as Record<string, unknown>).content,
        ).includes(token),
      );

      if (!persistedAssistantHasToken) {
        const persistedTypes = messages
          .map((message) => `${message.message_type}:${message.id}`)
          .join(", ");
        throw new Error(
          `Run ${runId} streamed ${token} but did not persist a matching assistant_message. ` +
            `Persisted messages: ${persistedTypes || "(none)"}`,
        );
      }
    },
    { timeout: 150000 },
  );
});
