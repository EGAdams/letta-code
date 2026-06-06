import { RemoteLogger } from "../../../logger/RemoteLogger";
import type { ITestLogger } from "../ITestLogger";

/**
 * Wraps RemoteLogger and forwards every call to the console too.
 * All remote-API failures are swallowed so the logger never fails a test.
 */
export class RemoteTestLogger implements ITestLogger {
  private readonly remote: RemoteLogger;
  private readonly prefix: string;

  constructor(loggerId: string, prefix?: string) {
    this.remote = new RemoteLogger(loggerId);
    this.prefix = prefix ? `[${prefix}] ` : "";
  }

  /** Call once after construction. Throws on failure so the caller can fall back to NullTestLogger. */
  async init(): Promise<void> {
    await this.remote.init();
  }

  async log(message: string): Promise<void> {
    console.log(`${this.prefix}${message}`);
    try {
      await this.remote.log(message);
    } catch {
      // best-effort
    }
  }

  async clearLogs(initialMessage?: string): Promise<void> {
    try {
      await this.remote.clearLogs(initialMessage);
    } catch {
      // best-effort
    }
  }

  async flush(): Promise<void> {
    try {
      await this.remote.flushLogs();
    } catch {
      // best-effort
    }
  }
}
