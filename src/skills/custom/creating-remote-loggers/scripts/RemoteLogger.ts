/**
 * RemoteLogger — persists structured log entries to the PHP monitored_objects API.
 *
 * Usage:
 *   const logger = new RemoteLogger("MyFeature_" + Math.floor(Date.now() / 1000));
 *   await logger.init();          // loads existing log or creates a fresh record
 *   await logger.log("step 1");   // appends entry and persists
 *   await logger.destroy();       // optional: remove the record when done
 */

const BASE_URL =
  "https://americansjewelry.com/libraries/local-php-api/index.php";

interface LogEntry {
  timestamp: number;
  id: string;
  message: string;
  method: string;
}

interface LoggerState {
  logObjects: LogEntry[];
  object_view_id: string;
}

export class RemoteLogger {
  private objectViewId: string;
  private logObjects: LogEntry[] = [];

  constructor(objectViewId: string) {
    this.objectViewId = objectViewId;
  }

  async init(): Promise<void> {
    const res = await fetch(
      `${BASE_URL}/object/select/${encodeURIComponent(this.objectViewId)}`,
    );
    if (res.ok) {
      const data = (await res.json()) as Record<string, unknown> | null;
      if (data && !data.error && data.object_data) {
        const state = JSON.parse(data.object_data as string) as LoggerState;
        this.logObjects = state.logObjects ?? [];
        return;
      }
    }
    await this._save("insert");
  }

  async log(message: string): Promise<void> {
    const ts = Math.floor(Date.now() / 1000);
    const rand = Math.floor(Math.random() * 1e15);
    const entry: LogEntry = {
      timestamp: ts,
      id: `${this.objectViewId}_${rand}_${ts}`,
      message,
      method: "createLogObject",
    };
    this.logObjects.push(entry);
    await this._save("update");
  }

  async destroy(): Promise<void> {
    await fetch(`${BASE_URL}/object/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ object_view_id: this.objectViewId }),
    });
  }

  private async _save(action: "insert" | "update"): Promise<void> {
    const state: LoggerState = {
      logObjects: this.logObjects,
      object_view_id: this.objectViewId,
    };
    const res = await fetch(`${BASE_URL}/object/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        object_view_id: this.objectViewId,
        object_data: JSON.stringify(state),
      }),
    });
    if (!res.ok) {
      throw new Error(
        `[RemoteLogger] ${action} failed with HTTP ${res.status}`,
      );
    }
  }
}
