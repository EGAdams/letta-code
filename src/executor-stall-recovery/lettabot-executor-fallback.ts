/**
 * executor_run fallback using ExecutorRunService for classified failure recovery
 * Drop-in replacement for lettabot/src/core/executor-fallback.ts
 */

import { HttpExecutorClient } from "./adapters/http-executor-client";
import {
  type TelegramAdapter,
  TelegramAlertSink,
} from "./adapters/telegram-alert-sink";
import type { ExecutorCommand } from "./models";
import { ExecutorRunService, StalledError } from "./service";

interface ExecutorRunArgs {
  command: string;
  cwd?: string;
}

// Mirrors lettabot's `core/multi-agent-fallback` PendingMultiAgentToolCall shape.
interface PendingMultiAgentToolCall {
  toolName: string;
  toolArgs: string;
}

// Singleton service instance (created once at bot startup)
let executorService: ExecutorRunService | null = null;

export function initializeExecutorService(
  telegramAdapter: TelegramAdapter,
  chatId: string,
  threadId?: string,
) {
  const client = new HttpExecutorClient("http://127.0.0.1:8787", 30000);
  const alertSink = new TelegramAlertSink(
    telegramAdapter,
    chatId,
    threadId,
    `${process.env.HOME || "/home/adamsl"}/.letta/scissari-alerts.jsonl`,
  );
  executorService = new ExecutorRunService(client, alertSink);
}

/**
 * Execute executor_run with classified failure recovery.
 * Returns the command output on success, or an error message.
 * Throws StalledError if the command cannot recover from failures.
 */
export async function executeExecutorRunFallback(
  call: PendingMultiAgentToolCall,
  agentId: string = "scissari",
): Promise<string | null> {
  if (call.toolName !== "executor_run") {
    return null;
  }

  if (!executorService) {
    return "executor_run: service not initialized (call initializeExecutorService first)";
  }

  let args: ExecutorRunArgs;
  try {
    args = JSON.parse(call.toolArgs);
  } catch (e) {
    console.error("[ExecutorService] Failed to parse executor_run args:", e);
    return "executor_run: invalid JSON arguments";
  }

  const { command, cwd } = args;
  if (!command || typeof command !== "string") {
    return "executor_run: missing required command argument";
  }

  try {
    console.log(
      "[ExecutorService] Executing with recovery: command=",
      command.slice(0, 60),
    );

    const cmd: ExecutorCommand = {
      cmd: command,
      cwd,
      timeout_s: 30,
    };

    const response = await executorService.execute(cmd, agentId);
    return response.stdout || response.stderr || "(executor_run completed)";
  } catch (error) {
    if (error instanceof StalledError) {
      // Classified failure — alert was already sent by the service
      // Return the concrete reason to the agent
      return `executor_run stalled: ${error.report.message}`;
    }

    // Unclassified error
    const msg = error instanceof Error ? error.message : String(error);
    console.error("[ExecutorService] Unclassified executor_run error:", msg);
    return `executor_run error: ${msg}`;
  }
}

export { StalledError, ExecutorRunService };
