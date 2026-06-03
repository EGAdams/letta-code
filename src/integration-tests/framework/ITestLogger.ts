/**
 * Null-Object pattern: tests call log/flush unconditionally.
 * NullTestLogger is returned when the remote logger fails to init.
 */
export interface ITestLogger {
  log(message: string): Promise<void>;
  /** Reset the viewer LED and set an initial status message. */
  clearLogs(initialMessage?: string): Promise<void>;
  flush(): Promise<void>;
}
