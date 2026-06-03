import { test } from "bun:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { settingsManager } from "../../settings-manager";
import type { IAgentUnderTest } from "./IAgentUnderTest";
import type { IStreamEventParser } from "./IStreamEventParser";
import type { ITestLogger } from "./ITestLogger";
import { NullTestLogger } from "./loggers/NullTestLogger";
import { RemoteTestLogger } from "./loggers/RemoteTestLogger";
import { LettaStreamParser } from "./parsers/LettaStreamParser";
import { BidirectionalRunner } from "./runners/BidirectionalRunner";
import { JsonOutputRunner } from "./runners/JsonOutputRunner";
import { StarvationRunner } from "./runners/StarvationRunner";
import { StreamJsonRunner } from "./runners/StreamJsonRunner";

const projectRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);

export interface StreamRunnerOptions {
  new?: boolean;
  yolo?: boolean;
  includePartialMessages?: boolean;
  memfsStartup?: "skip" | "run";
  timeoutMs?: number;
}

export interface JsonRunnerOptions {
  conversation?: string;
  timeoutMs?: number;
  retryOnTimeouts?: number;
}

export interface BidirectionalRunnerOptions {
  timeoutMs?: number;
}

export interface StarvationRunnerOptions {
  starvationTimeoutMs?: number;
  maxTotalTimeMs?: number;
  new?: boolean;
  includePartialMessages?: boolean;
  memfsStartup?: "skip" | "run";
}

/**
 * Abstract Factory that wires agent configuration into all test utilities.
 * Tests receive a pre-configured context and never hard-code agent IDs or URLs.
 *
 * Usage:
 *   const ctx = new AgentTestContext(ScissariAgent);
 *   ctx.maybeTest("name", async () => {
 *     const runner = ctx.createStreamRunner();
 *     const result = await runner.run("Hello");
 *     const events = ctx.parser.parseLines(result.stdout);
 *     ...
 *   }, { timeout: 60_000 });
 */
export class AgentTestContext {
  readonly parser: IStreamEventParser;

  constructor(private readonly agent: IAgentUnderTest) {
    this.parser = new LettaStreamParser();
  }

  /**
   * Returns the real `test` function when the agent's enable flag is set, otherwise test.skip.
   * Mirrors the `maybeTest` pattern used throughout the original test files.
   */
  get maybeTest(): typeof test {
    return process.env[this.agent.enableFlag] === "1"
      ? test
      : (test.skip as typeof test);
  }

  /** Convenience accessor for the agent config (agent ID, display name, etc.). */
  get config(): IAgentUnderTest {
    return this.agent;
  }

  /**
   * Sets LETTA_BASE_URL and LETTA_API_KEY in the current process env (if not already set)
   * then initializes settingsManager. Required before any test that calls getClient() directly.
   */
  async initSettings(): Promise<void> {
    process.env.LETTA_BASE_URL =
      process.env.LETTA_BASE_URL ?? this.agent.baseUrl;
    process.env.LETTA_API_KEY = process.env.LETTA_API_KEY ?? this.agent.apiKey;
    await settingsManager.initialize();
  }

  private get resolvedBaseUrl(): string {
    return process.env.LETTA_BASE_URL ?? this.agent.baseUrl;
  }

  private get resolvedApiKey(): string {
    return process.env.LETTA_API_KEY ?? this.agent.apiKey;
  }

  /** Strategy: --output-format stream-json, resolves on {type:"result"}. */
  createStreamRunner(opts: StreamRunnerOptions = {}): StreamJsonRunner {
    return new StreamJsonRunner({
      agentId: this.agent.agentId,
      baseUrl: this.resolvedBaseUrl,
      apiKey: this.resolvedApiKey,
      projectRoot,
      newConversation: opts.new ?? true,
      yolo: opts.yolo ?? false,
      includePartialMessages: opts.includePartialMessages ?? true,
      memfsStartup: opts.memfsStartup ?? "skip",
      timeoutMs: opts.timeoutMs ?? 120_000,
    });
  }

  /** Strategy: --output-format json, waits for process exit. */
  createJsonRunner(opts: JsonRunnerOptions = {}): JsonOutputRunner {
    return new JsonOutputRunner({
      agentId: this.agent.agentId,
      baseUrl: this.resolvedBaseUrl,
      apiKey: this.resolvedApiKey,
      projectRoot,
      conversation: opts.conversation ?? "default",
      timeoutMs: opts.timeoutMs ?? 300_000,
      retryOnTimeouts: opts.retryOnTimeouts ?? 1,
    });
  }

  /** Strategy: bidirectional stdin/stdout stream-json with auto-approval. */
  createBidirectionalRunner(
    opts: BidirectionalRunnerOptions = {},
  ): BidirectionalRunner {
    return new BidirectionalRunner({
      agentId: this.agent.agentId,
      baseUrl: this.resolvedBaseUrl,
      apiKey: this.resolvedApiKey,
      projectRoot,
      timeoutMs: opts.timeoutMs ?? 95_000,
    });
  }

  /** Strategy: stream-json with output-starvation detection (planning-mode hang). */
  createStarvationRunner(opts: StarvationRunnerOptions = {}): StarvationRunner {
    return new StarvationRunner({
      agentId: this.agent.agentId,
      baseUrl: this.resolvedBaseUrl,
      apiKey: this.resolvedApiKey,
      projectRoot,
      starvationTimeoutMs: opts.starvationTimeoutMs ?? 45_000,
      maxTotalTimeMs: opts.maxTotalTimeMs ?? 120_000,
      newConversation: opts.new ?? false,
      includePartialMessages: opts.includePartialMessages ?? true,
      memfsStartup: opts.memfsStartup ?? "skip",
    });
  }

  /**
   * Creates a test logger. Falls back to NullTestLogger if the remote API is unreachable,
   * so logger failures never cause test failures.
   */
  async createLogger(loggerId: string, prefix?: string): Promise<ITestLogger> {
    const logger = new RemoteTestLogger(
      loggerId,
      prefix ?? this.agent.displayName.toLowerCase(),
    );
    try {
      await logger.init();
      return logger;
    } catch {
      console.warn(
        `[AgentTestContext] RemoteLogger init failed for ${loggerId} — continuing without remote logging`,
      );
      return new NullTestLogger();
    }
  }
}
