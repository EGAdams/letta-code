import { describe, test } from "bun:test";
import { getClient } from "../agent/client";
import { settingsManager } from "../settings-manager";

const SCISSARI_AGENT_ID = "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa";
const DEFAULT_BASE_URL = "http://100.80.49.10:8283";
const TEST_API_KEY = "6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8";

type MessageLike = Record<string, unknown>;

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

async function sendTelegramMessage(
  botToken: string,
  chatId: string,
  text: string,
): Promise<void> {
  const res = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });

  const body = await res.text();
  if (!res.ok) {
    throw new Error(`Telegram sendMessage failed (${res.status}): ${body}`);
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(body) as Record<string, unknown>;
  } catch {
    throw new Error(`Telegram sendMessage returned non-JSON body: ${body}`);
  }

  if (parsed.ok !== true) {
    throw new Error(`Telegram sendMessage returned ok=false: ${body}`);
  }
}

async function waitForScissariMessage(
  token: string,
  timeoutMs: number,
): Promise<void> {
  const client = await getClient();
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    const page = await client.agents.messages.list(SCISSARI_AGENT_ID, {
      limit: 50,
    });
    const messages = page.getPaginatedItems() as unknown as MessageLike[];
    const matched = messages.some((message) =>
      messageContentText(message.content).includes(token),
    );
    if (matched) return;

    await Bun.sleep(3000);
  }

  throw new Error(
    `Timed out waiting for Telegram message token in Scissari history: ${token}`,
  );
}

describe("Scissari Telegram connection integration", () => {
  const envReady =
    process.env.LETTA_RUN_SCISSARI_TEST === "1" &&
    Boolean(
      process.env.SCISSARI_TELEGRAM_CHAT_ID &&
        (process.env.SCISSARI_TELEGRAM_BOT_TOKEN || process.env.TELEGRAM_TOKEN),
    );
  const maybeTest = envReady ? test : test.skip;

  maybeTest(
    "Telegram bridge delivers inbound messages into Scissari",
    async () => {
      process.env.LETTA_BASE_URL =
        process.env.LETTA_BASE_URL ?? DEFAULT_BASE_URL;
      process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? TEST_API_KEY;
      await settingsManager.initialize();

      const botToken =
        process.env.SCISSARI_TELEGRAM_BOT_TOKEN ?? process.env.TELEGRAM_TOKEN;
      const chatId = process.env.SCISSARI_TELEGRAM_CHAT_ID;

      const token = `SCISSARI_TELEGRAM_${Date.now()}`;
      const message = `[IntegrationTest] ${token}`;

      await sendTelegramMessage(botToken!, chatId!, message);
      await waitForScissariMessage(token, 120000);
    },
    { timeout: 150000 },
  );
});
