import { RemoteLogger } from "../logger/RemoteLogger";
import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

const LETTA_BASE_URL = process.env.LETTA_BASE_URL ?? "http://100.80.49.10:8283";

async function main() {
  const logger = new RemoteLogger("OAuthHealthCheck_2026");

  const exitOnLoggerFailure = (context: string, err: unknown): never => {
    const detail = err instanceof Error ? err.message : String(err);
    console.error(`[oauth-health] ${context}: ${detail}`);
    process.exit(1);
  };

  console.log("[oauth-health] Initializing OAuthHealthCheck_2026...");
  try {
    await logger.init();
    await logger.clearLogs("OAuthHealthCheck ready.");
    console.log("[oauth-health] Logger initialized");
  } catch (err) {
    exitOnLoggerFailure("Logger init FAILED", err);
  }

  const log = async (msg: string) => {
    console.log(`[oauth-health] ${msg}`);
    try {
      await logger.log(msg);
    } catch (err) {
      exitOnLoggerFailure("remote log FAILED", err);
    }
  };

  await log("OAuthHealthCheck started");
  await log(`Letta server: ${LETTA_BASE_URL}`);

  // 1. Check ~/.codex/auth.json
  await log("--- Checking ~/.codex/auth.json ---");
  try {
    const authPath = join(homedir(), ".codex", "auth.json");
    const raw = await readFile(authPath, "utf8");
    const auth = JSON.parse(raw) as Record<string, unknown>;
    await log(`auth_mode: ${auth.auth_mode ?? "(missing)"}`);
    await log(`OPENAI_API_KEY: ${auth.OPENAI_API_KEY === null ? "null (correct)" : String(auth.OPENAI_API_KEY ?? "(missing)")}`);
    const lastRefresh = auth.last_refresh;
    await log(`last_refresh: ${lastRefresh ? String(lastRefresh) : "(missing)"}`);
    const hasAccessToken = typeof auth.access_token === "string" && auth.access_token.length > 0;
    const hasIdToken = typeof auth.id_token === "string" && auth.id_token.length > 0;
    await log(`access_token present: ${hasAccessToken}`);
    await log(`id_token present: ${hasIdToken}`);
  } catch (err) {
    await log(`~/.codex/auth.json ERROR: ${err instanceof Error ? err.message : String(err)}`);
  }

  // 2. Check registered providers on Letta server
  await log("--- Checking /v1/providers ---");
  try {
    const res = await fetch(`${LETTA_BASE_URL}/v1/providers`);
    await log(`GET /v1/providers → HTTP ${res.status}`);
    if (res.ok) {
      const providers = await res.json() as Array<Record<string, unknown>>;
      if (providers.length === 0) {
        await log("ERROR: No providers registered on server");
      } else {
        for (const p of providers) {
          await log(`  provider: ${p.provider_name ?? p.name} type=${p.provider_type}`);
        }
        const hasChatgpt = providers.some(
          (p) => p.provider_name === "chatgpt-plus-pro" || p.provider_type === "chatgpt_oauth"
        );
        await log(`chatgpt-plus-pro registered: ${hasChatgpt ? "YES" : "NO — run /connect chatgpt"}`);
      }
    } else {
      const text = await res.text();
      await log(`ERROR response: ${text.slice(0, 200)}`);
    }
  } catch (err) {
    await log(`/v1/providers ERROR: ${err instanceof Error ? err.message : String(err)}`);
  }

  // 3. Check available models on Letta server
  await log("--- Checking /v1/models ---");
  try {
    const res = await fetch(`${LETTA_BASE_URL}/v1/models`);
    await log(`GET /v1/models → HTTP ${res.status}`);
    if (res.ok) {
      const models = await res.json() as Array<Record<string, unknown>>;
      await log(`Total models listed: ${models.length}`);
      if (models.length === 0) {
        await log("ERROR: Server lists zero models — provider not registered or server misconfigured");
      } else {
        const providers = [...new Set(models.map((m) => String(m.provider_name ?? m.provider ?? "")))];
        await log(`Providers with models: ${providers.join(", ")}`);
      }
    } else {
      const text = await res.text();
      await log(`ERROR response: ${text.slice(0, 200)}`);
    }
  } catch (err) {
    await log(`/v1/models ERROR: ${err instanceof Error ? err.message : String(err)}`);
  }

  // 4. Check env for stray OPENAI_API_KEY
  await log("--- Checking environment ---");
  const envKey = process.env.OPENAI_API_KEY;
  if (envKey) {
    await log(`WARNING: OPENAI_API_KEY is set in env (${envKey.slice(0, 8)}...) — remove from ~/.bashrc`);
  } else {
    await log("OPENAI_API_KEY not in env (correct)");
  }

  await log("OAuthHealthCheck finished");
  console.log("[oauth-health] Done. Check the viewer at http://localhost:8080");
}

main().catch((err) => {
  const detail = err instanceof Error ? err.stack ?? err.message : String(err);
  console.error(`[oauth-health] Unhandled error: ${detail}`);
  process.exit(1);
});
