/**
 * IAlertSink implementation sending executor stall alerts to Telegram
 */

import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import type { IAlertSink } from "../interfaces";
import type { StallReport } from "../models";

export interface TelegramAdapter {
  sendMessage(opts: {
    chatId: string;
    text: string;
    threadId?: string;
  }): Promise<void>;
}

export class TelegramAlertSink implements IAlertSink {
  private adapter: TelegramAdapter;
  private chatId: string;
  private threadId?: string;
  private jsonlPath?: string;

  constructor(
    adapter: TelegramAdapter,
    chatId: string,
    threadId?: string,
    jsonlPath?: string,
  ) {
    this.adapter = adapter;
    this.chatId = chatId;
    this.threadId = threadId;
    this.jsonlPath = jsonlPath;
  }

  async emit(report: StallReport): Promise<void> {
    // Log to JSONL for forensics
    if (this.jsonlPath) {
      try {
        mkdirSync(dirname(this.jsonlPath), { recursive: true });
        appendFileSync(
          this.jsonlPath,
          `${JSON.stringify({
            timestamp: new Date().toISOString(),
            severity: "critical",
            event: "executor_stall",
            agent_id: report.agent_id,
            classification: report.classification,
            calls_used: report.calls_used,
            final_state: report.final_state,
          })}\n`,
        );
      } catch {
        // Best effort
      }
    }

    // Send alert to Telegram
    try {
      await this.adapter.sendMessage({
        chatId: this.chatId,
        text: `🚨 ${report.message}`,
        threadId: this.threadId,
      });
    } catch (error) {
      console.error("[AlertSink] Failed to send Telegram alert:", error);
      // Don't throw — alerting failure shouldn't crash the bot
    }
  }
}
