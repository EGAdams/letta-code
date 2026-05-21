/**
 * LettaLogger — sends structured log entries to the americansjewelry.com PHP API.
 *
 * Each class gets one envelope row in monitored_objects keyed by objectViewId
 * (convention: ClassName_Year, e.g. "LettaClient_2026").
 *
 * objectData is a JSON-encoded array of log entries that is fully replaced on
 * every flush.  Logging never throws — failures are silently swallowed so they
 * cannot crash the host object.
 */

const BASE_URL =
  "https://americansjewelry.com/libraries/local-php-api/index.php/object";
const TIMEOUT_MS = 5000;

export type LogStatus = "green" | "yellow" | "red";

interface LogEntry {
  timestamp: string;
  method: string;
  event: string;
  status: LogStatus;
  data?: unknown;
}

export class LettaLogger {
  private readonly objectViewId: string;
  private entries: LogEntry[] = [];

  constructor(objectViewId: string) {
    this.objectViewId = objectViewId;
  }

  // --------------------------------------------------------------------
  // Public API
  // --------------------------------------------------------------------

  log(
    method: string,
    event: string,
    data?: unknown,
    status: LogStatus = "green",
  ): void {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      method,
      event,
      status,
      ...(data !== undefined ? { data } : {}),
    };
    this.entries.push(entry);
    this.flush().catch(() => {}); // fire-and-forget, never throws
  }

  // --------------------------------------------------------------------
  // Internal
  // --------------------------------------------------------------------

  private async flush(): Promise<void> {
    const payload = JSON.stringify({
      object_view_id: this.objectViewId,
      object_data: JSON.stringify(this.entries),
    });

    const inserted = await this.post("/insert", payload);
    if (!inserted) {
      await this.post("/update", payload);
    }
  }

  /** Returns true if insert succeeded (response contains "insert success"). */
  private async post(path: string, payload: string): Promise<boolean> {
    try {
      const res = await fetch(BASE_URL + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        signal: AbortSignal.timeout(TIMEOUT_MS),
      });
      const text = await res.text();
      return text.includes("insert success");
    } catch {
      return false;
    }
  }
}
