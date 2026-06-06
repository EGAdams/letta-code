import type { ITestLogger } from "../ITestLogger";

/** Returned when RemoteLogger fails to initialize. Tests proceed without remote logging. */
export class NullTestLogger implements ITestLogger {
  async log(_message: string): Promise<void> {}
  async clearLogs(_initialMessage?: string): Promise<void> {}
  async flush(): Promise<void> {}
}
