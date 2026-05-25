import type { IAgentEventLogger } from "./agent-event-logger";
import { RemoteLogger } from "./RemoteLogger";

// Concrete IAgentEventLogger backed by RemoteLogger.
export class RemoteAgentEventLogger implements IAgentEventLogger {
  private readonly inner: RemoteLogger;

  constructor(loggerId: string) {
    this.inner = new RemoteLogger(loggerId);
  }

  async init(): Promise<void> {
    await this.inner.init();
  }

  async log(message: string): Promise<void> {
    await this.inner.log(message);
  }

  async clear(label = "ready."): Promise<void> {
    await this.inner.clearLogs(label);
  }
}
