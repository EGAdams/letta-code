/**
 * Integration test: Scissari web-tool response.
 *
 * Bug scenario (2026-05-27):
 *   1. Scissari calls web_fetch_exa (server-side Exa MCP tool) multiple times.
 *   2. Letta 0.16.7 does NOT stream tool_return_message events for server-side
 *      MCP tools — pendingServerToolCalls in lettabot stayed non-empty at stream end.
 *   3. lettabot was incorrectly attempting multi-agent fallback for web_fetch_exa
 *      (not a multi-agent tool), producing 3× "no response" warnings.
 *   4. Continuation turn also called web_fetch_exa (with empty args) → empty result.
 *   5. lettabot returned the misleading "message path to the other agent stalled" error.
 *
 * Fix (in lettabot/src/core/bot.ts):
 *   - Skip client-side fallback for server-side tools (not in CLIENT_SIDE_FALLBACK_TOOLS).
 *   - Continuation prompt now includes <system-reminder> to block further tool calls.
 *   - Stalled message reworded to not say "message path to the other agent".
 *
 * This test verifies that the letta-code CLI returns a user-visible answer (not the
 * stall error string) when Scissari is asked to fetch a URL.
 *
 * To run: LETTA_RUN_SCISSARI_TEST=1 bun test scissari-web-tool-response
 */

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
const LOGGER_ID = "ScissariWebToolResponse_2026";

// A URL that is known to exist and return content via Exa.
const TEST_URL =
  "https://americansjewelry.com/americanjewelry_live_upload_guide.html";

// The stalled-response error strings returned by lettabot when it can't get a
// user-visible answer after web-tool usage. Both old and new wording detected.
const STALL_ERROR_FRAGMENTS = [
  "message path to the other agent likely stalled",
  "I ran into an issue completing that request",
  "response was lost during a tool workflow",
];

function isStallError(text: string): boolean {
  const lower = text.toLowerCase();
  return STALL_ERROR_FRAGMENTS.some((s) => lower.includes(s.toLowerCase()));
}

type JsonObj = Record<string, unknown>;

function parseJsonLines(stdout: string): JsonObj[] {
  return stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .flatMap((line) => {
      try {
        return [JSON.parse(line) as JsonObj];
      } catch {
        return [];
      }
    });
}

function extractResultText(events: JsonObj[]): string {
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i] as JsonObj;
    if (
      ev.type === "result" &&
      typeof ev.result === "string" &&
      ev.result.trim()
    ) {
      return ev.result as string;
    }
  }
  return "";
}

function extractMessageText(events: JsonObj[]): string {
  const parts: string[] = [];
  for (const ev of events) {
    if (ev.type === "message" && ev.message_type === "assistant_message") {
      const content = ev.content;
      if (typeof content === "string") parts.push(content);
      else if (Array.isArray(content)) {
        for (const part of content) {
          if (
            part &&
            typeof part === "object" &&
            "text" in part &&
            typeof part.text === "string"
          ) {
            parts.push(part.text);
          }
        }
      }
    }
  }
  return parts.join("");
}

async function runCliPrompt(
  prompt: string,
): Promise<{ stdout: string; exitCode: number | null }> {
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
          LETTA_DEBUG: "0",
        },
        stdio: ["pipe", "pipe", "pipe"],
      },
    );

    let stdout = "";
    proc.stdout?.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });

    proc.on("close", (code) => {
      resolve({ stdout, exitCode: code });
    });
    proc.on("error", reject);

    setTimeout(() => {
      try {
        proc.kill();
      } catch {
        // ignore
      }
      resolve({ stdout, exitCode: null });
    }, 90_000);
  });
}

describe("Scissari web tool response", () => {
  beforeEach(async () => {
    await resetAllLoggers();
  }, 30000);

  const maybeTest =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" ? test : test.skip;

  // Verify that Scissari can call web_fetch_exa (server-side Exa MCP tool)
  // and still produce a user-visible answer via letta-code.
  // Catches the 2026-05-27 regression where lettabot returned the stalled-
  // message fallback every time Scissari did web research.
  maybeTest(
    "web_fetch_exa call via letta-code produces a user-visible response, not a stall error",
    async () => {
      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        await logger.clearLogs("ScissariWebToolResponse test started.");
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[web-tool-response] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }

      const log = async (message: string) => {
        console.log(`[web-tool-response] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch {
          // best-effort
        }
      };

      const prompt = `Fetch this URL and tell me the first section heading: ${TEST_URL}`;
      await log(`Prompt: ${prompt}`);

      const { stdout, exitCode } = await runCliPrompt(prompt);
      const events = parseJsonLines(stdout);

      const resultText = extractResultText(events);
      const messageText = extractMessageText(events);
      const responseText = resultText || messageText;

      await log(
        `exit=${exitCode} events=${events.length} resultLen=${resultText.length} msgLen=${messageText.length}`,
      );
      await log(`Result preview: ${responseText.slice(0, 200)}`);

      // Verify the CLI exited successfully.
      expect(exitCode).toBe(0);

      // Verify a non-empty response was produced.
      expect(responseText.trim().length).toBeGreaterThan(0);

      // Core assertion: the response must NOT be the stall error.
      // This catches the 2026-05-27 regression in lettabot's continuation logic.
      if (isStallError(responseText)) {
        await log(
          `ERROR: response is a stall error: ${responseText.slice(0, 200)}`,
        );
      }
      expect(isStallError(responseText)).toBe(false);

      await log(
        `PASS: Scissari returned user-visible text (${responseText.length} chars) without stall error`,
      );

      if (loggerReady) await logger.flushLogs();
    },
    { timeout: 120_000 },
  );

  // Verify that the Exa MCP tool is registered and attached to Scissari.
  // Catches Exa API key expiry or tool de-registration.
  maybeTest(
    "Exa MCP tool is registered and attached to Scissari",
    async () => {
      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      const logger = new RemoteLogger(LOGGER_ID);
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch {
        // non-fatal
      }

      const log = async (message: string) => {
        console.log(`[web-tool-exa-health] ${message}`);
        if (!loggerReady) return;
        try {
          await logger.log(message);
        } catch {
          // best-effort
        }
      };

      const client = await getClient();

      try {
        // Confirm web_fetch_exa is registered as an external_mcp tool.
        const toolsPage = await client.tools.list({
          name: "web_fetch_exa",
          limit: 5,
        });
        const tool = toolsPage.items.find((t) => t.name === "web_fetch_exa");
        expect(tool).toBeDefined();
        expect(tool?.tool_type).toBe("external_mcp");
        await log(
          `web_fetch_exa found: id=${tool?.id} type=${tool?.tool_type}`,
        );

        // Confirm Scissari has the tool attached.
        const agentToolsPage = await client.agents.tools.list(
          SCISSARI_AGENT_ID,
          { limit: 50 },
        );
        const attached = agentToolsPage.getPaginatedItems().map((t) => t.name);
        expect(attached).toContain("web_fetch_exa");
        await log(`web_fetch_exa attached to Scissari ✓`);

        await log("PASS: Exa MCP tool registered and attached to Scissari");
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      } finally {
        if (loggerReady) await logger.flushLogs();
      }
    },
    { timeout: 30_000 },
  );
});
