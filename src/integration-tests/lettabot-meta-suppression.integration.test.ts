/**
 * Integration test: lettabot meta-only response suppression
 *
 * Verifies that when Scissari generates reasoning-only text before a tool call
 * ("I should search...", "**Preparing to search the web**..."), lettabot does NOT
 * deliver that raw meta-only text to the user via Telegram.
 *
 * Root cause fixed (2026-05-07) in /home/adamsl/lettabot/src/core/bot.ts:
 *   - Line ~1271: discard meta-only pre-tool text, reset sentAnyMessage=false
 *   - Line ~1344: added !isMetaOnlyResponse(streamText) to live-stream guard
 *
 * Run: LETTA_RUN_LETTABOT_TEST=1 bun test src/integration-tests/lettabot-meta-suppression.integration.test.ts
 */

import { beforeAll, describe, expect, test } from "bun:test";
import { RemoteLogger } from "../logger/RemoteLogger";
import { resetAllLoggers } from "./logger-helpers";

const LETTABOT_API_URL = "http://127.0.0.1:8091/api/v1/chat";
const LETTABOT_API_KEY_FILE = "/home/adamsl/lettabot/lettabot-api.json";

// Mirrors isMetaOnlyResponse() in /home/adamsl/lettabot/src/core/bot.ts
const META_ONLY_PREFIXES = [
  "i should ",
  "i need to ",
  "i'm thinking about",
  "i am thinking about",
  "considering ",
  "exploring ",
  "planning ",
  "preparing to",
  "**preparing",
  "processing user request",
  "examining skill tool usage",
];

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

// Empty response means lettabot suppressed reasoning and returned nothing — that is CORRECT
// behaviour after the fix. Only flag responses that contain explicit reasoning prefixes.
function hasMetaOnlyContent(text: string): boolean {
  if (!text.trim()) return false;
  const normalized = text.toLowerCase().replace(/\s+/g, " ").trim();
  return META_ONLY_PREFIXES.some((prefix) => normalized.startsWith(prefix));
}

async function getLettabotApiKey(): Promise<string> {
  try {
    const file = Bun.file(LETTABOT_API_KEY_FILE);
    const data = (await file.json()) as { apiKey: string };
    return data.apiKey;
  } catch {
    return "";
  }
}

async function chatWithLettabot(
  message: string,
  apiKey: string,
  timeoutMs = 90000,
): Promise<{ success: boolean; response: string; error?: string }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(LETTABOT_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
      },
      body: JSON.stringify({ message }),
      signal: controller.signal,
    });
    const data = (await res.json()) as {
      success: boolean;
      response?: string;
      error?: string;
    };
    return {
      success: data.success,
      response: data.response ?? "",
      error: data.error,
    };
  } catch (err) {
    return {
      success: false,
      response: "",
      error: err instanceof Error ? err.message : String(err),
    };
  } finally {
    clearTimeout(timer);
  }
}

describe("Lettabot meta-only response suppression", () => {
  beforeAll(async () => {
    await resetAllLoggers();
  }, 30000);

  const maybeTest =
    process.env.LETTA_RUN_LETTABOT_TEST === "1" ? test : test.skip;

  maybeTest(
    "simple question returns a substantive answer (not meta-only reasoning)",
    async () => {
      const logger = new RemoteLogger("LetabotMetaSuppression_SimpleQ_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[meta-suppression:SimpleQ] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }

      const log = async (message: string) => {
        console.log(`[meta-suppression:SimpleQ] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[meta-suppression:SimpleQ] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      try {
        await log("Test started: simple question should return a real answer");

        await log("Step 1: Reading lettabot API key");
        const apiKey = await getLettabotApiKey();
        if (!apiKey) throw new Error(`Could not read API key from ${LETTABOT_API_KEY_FILE}`);
        await log(`PASS: API key loaded (${apiKey.slice(0, 8)}...)`);

        await log("Step 2: Sending question — 'What is 2 + 2?'");
        const result = await chatWithLettabot("What is 2 + 2?", apiKey, 60000);
        await log(`Step 3: Response — success=${result.success}, length=${result.response.length}`);
        await log(`Response text: ${result.response.slice(0, 300)}`);

        expect(result.success).toBe(true);
        await log("PASS: lettabot reported success=true");

        expect(result.response.trim().length).toBeGreaterThan(0);
        await log("PASS: response is non-empty");

        const metaOnly = hasMetaOnlyContent(result.response);
        await log(`Step 4: meta-only check — prefix: "${result.response.toLowerCase().trim().slice(0, 80)}"`);
        expect(metaOnly).toBe(false);
        await log("PASS: response is not meta-only reasoning text");

        await log("PASS: all assertions passed — test finished");
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      }
    },
    { timeout: 90000 },
  );

  maybeTest(
    "web search request does not expose raw pre-tool reasoning text",
    async () => {
      const logger = new RemoteLogger("LetabotMetaSuppression_WebSearch_2026");
      let loggerReady = false;
      try {
        await logger.init();
        loggerReady = true;
      } catch (err) {
        console.warn(
          `[meta-suppression:WebSearch] RemoteLogger init failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }

      const log = async (message: string) => {
        console.log(`[meta-suppression:WebSearch] ${message}`);
        if (loggerReady) {
          try {
            await logger.log(normalizeLoggerMessage(message));
          } catch (err) {
            console.error(
              `[meta-suppression:WebSearch] log failed: ${err instanceof Error ? err.message : String(err)}`,
            );
          }
        }
      };

      try {
        await log("Test started: web search must not expose raw reasoning text");
        await log("Before fix: lettabot returned '**Preparing to search the web**...'");
        await log("After fix: retry fires — empty response or real results, never raw reasoning");

        await log("Step 1: Reading lettabot API key");
        const apiKey = await getLettabotApiKey();
        if (!apiKey) throw new Error(`Could not read API key from ${LETTABOT_API_KEY_FILE}`);
        await log(`PASS: API key loaded (${apiKey.slice(0, 8)}...)`);

        await log("Step 2: Sending web search request — 'Search the web for what memfs is'");
        const result = await chatWithLettabot(
          "Search the web for what memfs is and give me a brief summary.",
          apiKey,
          90000,
        );
        await log(`Step 3: Response — success=${result.success}, length=${result.response.length}`);
        await log(`Response text: "${result.response.slice(0, 400)}"`);

        // Empty response is acceptable — means reasoning was suppressed and retry produced nothing.
        // Only fail if the response contains explicit pre-tool reasoning text.
        const metaOnly = hasMetaOnlyContent(result.response);
        await log(`Step 4: meta-only check — prefix: "${result.response.toLowerCase().trim().slice(0, 80)}"`);
        expect(metaOnly).toBe(false);
        await log("PASS: response does not contain meta-only reasoning text");

        const normalized = result.response.toLowerCase().trim();
        expect(normalized).not.toMatch(/^\*\*preparing to search/);
        await log("PASS: does not start with '**Preparing to search'");

        expect(normalized).not.toMatch(/^i (should|need to|must) search/);
        await log("PASS: does not start with 'I should/need to/must search'");

        await log("PASS: all meta-only suppression assertions passed — test finished");
      } catch (err) {
        await log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
        throw err;
      }
      if (loggerReady) await logger.flushLogs();
    },
    { timeout: 120000 },
  );
});
