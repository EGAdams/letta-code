/**
 * IExecutorClient implementation wrapping HTTP calls to executor service @ 127.0.0.1:8787
 */

import type { IExecutorClient } from "../interfaces";
import type { ExecutorCommand, ExecutorResponse } from "../models";
import { ExecutorFailureError } from "../models";

export class HttpExecutorClient implements IExecutorClient {
  private baseUrl: string;
  private timeoutMs: number;

  constructor(
    baseUrl: string = "http://127.0.0.1:8787",
    timeoutMs: number = 30000,
  ) {
    this.baseUrl = baseUrl;
    this.timeoutMs = timeoutMs;
  }

  async run(cmd: ExecutorCommand): Promise<ExecutorResponse> {
    try {
      const url = new URL(`${this.baseUrl}/run`);
      url.searchParams.set("command", cmd.cmd);
      if (cmd.cwd) {
        url.searchParams.set("cwd", cmd.cwd);
      }

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

      let response: Response;
      try {
        response = await fetch(url.toString(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
        });
      } finally {
        clearTimeout(timeoutId);
      }

      if (!response.ok) {
        const text = await response.text();
        throw new ExecutorFailureError({
          status: response.status,
          detail: text || `HTTP ${response.status}`,
        });
      }

      const json = (await response.json()) as Record<string, unknown>;
      return {
        ok: true,
        status: response.status,
        stdout: String(json.stdout || ""),
        stderr: String(json.stderr || ""),
        duration_s: Number(json.duration_s || 0),
      };
    } catch (error) {
      if (error instanceof ExecutorFailureError) {
        throw error;
      }

      // Network / timeout errors
      let transportError = "unknown error";
      if (error instanceof Error) {
        if (error.name === "AbortError") {
          transportError = `timeout after ${this.timeoutMs}ms`;
        } else {
          transportError = error.message;
        }
      }

      throw new ExecutorFailureError({
        transport_error: transportError,
        detail: String(error),
      });
    }
  }
}
