/*
 * Logger Interfaces to program to.
 */
const BASE_URL = "https://americansjewelry.com/libraries/local-php-api/index.php";

interface LogEntry {
  timestamp: number; // milliseconds since epoch — matches ILogObject
  id: string;
  message: string;
  method: string;
}

interface MonitorLedClassObject {
  background_color: string;
  text_align: string;
  margin_top: string;
  color: string;
}

interface MonitorLed {
  classObject: MonitorLedClassObject;
  ledText: string;
  RUNNING_COLOR: string;
  PASS_COLOR: string;
  FAIL_COLOR: string;
}

interface LoggerState {
  object_view_id: string;
  logObjects: LogEntry[];
  monitorLed: MonitorLed;
}

const RUNNING_COLOR = "lightyellow";
const PASS_COLOR    = "lightgreen";
const FAIL_COLOR    = "#fb6666";

function defaultLed(): MonitorLed {
  return {
    classObject: { background_color: RUNNING_COLOR, text_align: "left", margin_top: "2px", color: "black" },
    ledText:      "ready.",
    RUNNING_COLOR,
    PASS_COLOR,
    FAIL_COLOR,
  };
}

function updatedLed(message: string, current: MonitorLed): MonitorLed {
  const led: MonitorLed = {
    ...current,
    classObject: { ...defaultLed().classObject, ...(current.classObject ?? {}) },
    ledText: message,
  };
  // Match the viewer TypeScript trigger semantics exactly:
  // - PASS only when message includes lowercase "finished"
  // - FAIL only when message includes uppercase "ERROR"
  if (message.includes("finished")) {
    led.classObject.background_color = PASS_COLOR;
    led.classObject.color = "black";
  } else if (message.includes("ERROR")) {
    led.classObject.background_color = FAIL_COLOR;
    led.classObject.color = "white";
  } else {
    led.classObject.background_color = RUNNING_COLOR;
    led.classObject.color = "black";
  }
  return led;
}

export class RemoteLogger {
  private objectViewId: string;
  private logObjects: LogEntry[] = [];
  private monitorLed: MonitorLed;

  constructor(objectViewId: string) {
    this.objectViewId = objectViewId;
    this.monitorLed   = defaultLed();
  }

  async init(): Promise<void> {
    const state = await this._fetchExistingState();
    if (state) {
      this.logObjects = state.logObjects ?? [];
      const rawLed = state.monitorLed ?? defaultLed();
      this.monitorLed = rawLed.classObject
        ? rawLed
        : { ...rawLed, classObject: defaultLed().classObject };
      // Repair corrupted records (old shape missing classObject) immediately
      if (!state.monitorLed?.classObject) {
        await this._post("update");
      }
      return;
    }
    await this._post("insert");
  }

  async log(message: string): Promise<void> {
    const timestamp = Date.now(); // milliseconds — matches ILogObject
    const rand      = Math.floor(Math.random() * 1e13);
    this.logObjects.push({
      timestamp,
      id:      `${this.objectViewId}_${rand}_${timestamp}`,
      message,
      method:  "createLogObject",
    });
    this.monitorLed = updatedLed(message, this.monitorLed);
    await this._post("update");
  }

  async clearLogs(ledText = "ready."): Promise<void> {
    this.logObjects = [];
    this.monitorLed = {
      ...defaultLed(),
      ledText,
    };
    await this._post("update");
  }

  async destroy(): Promise<void> {
    await fetch(`${BASE_URL}/object/delete`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ object_view_id: this.objectViewId }),
    });
  }

  private _state(): LoggerState {
    return {
      object_view_id: this.objectViewId,
      logObjects:     this.logObjects,
      monitorLed:     this.monitorLed,
    };
  }

  private async _post(action: "insert" | "update"): Promise<void> {
    let res: Response;
    try {
      res = await fetch(`${BASE_URL}/object/${action}`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          object_view_id: this.objectViewId,
          object_data:    JSON.stringify(this._state()),
        }),
      });
    } catch (err) {
      if (await this._isStatePersisted()) {
        return;
      }
      throw new Error(
        `[RemoteLogger] ${action} failed before response: ${err instanceof Error ? err.message : String(err)}`,
      );
    }

    if (!res.ok) {
      // The production API can occasionally return HTTP 500 while still persisting.
      if (await this._isStatePersisted()) {
        return;
      }
      throw new Error(`[RemoteLogger] ${action} failed (HTTP ${res.status})`);
    }

    let body: unknown;
    try {
      body = (await res.json()) as unknown;
    } catch {
      if (await this._isStatePersisted()) {
        return;
      }
      throw new Error(`[RemoteLogger] ${action} failed (invalid JSON response)`);
    }

    if (body !== null && typeof body === "object" && (body as Record<string, unknown>)["error"]) {
      if (await this._isStatePersisted()) {
        return;
      }
      throw new Error(
        `[RemoteLogger] ${action} error: ${JSON.stringify(body)}`,
      );
    }
  }

  private async _fetchExistingState(): Promise<LoggerState | null> {
    try {
      const res = await fetch(
        `${BASE_URL}/object/select/${encodeURIComponent(this.objectViewId)}`,
      );
      if (res.ok) {
        const data = (await res.json()) as Record<string, unknown> | null;
        const parsed = this._parseSelectPayload(data);
        if (parsed) {
          return parsed;
        }
      }
    } catch {
      // Fallback below.
    }

    return this._fetchStateFromSelectAll();
  }

  private _parseSelectPayload(
    data: Record<string, unknown> | null,
  ): LoggerState | null {
    if (!data || data.error || !data.object_data) {
      return null;
    }
    try {
      return JSON.parse(data.object_data as string) as LoggerState;
    } catch {
      return null;
    }
  }

  private async _fetchStateFromSelectAll(): Promise<LoggerState | null> {
    try {
      const res = await fetch(`${BASE_URL}/object/selectAll`);
      if (!res.ok) {
        return null;
      }
      const rows = (await res.json()) as Array<Record<string, unknown>>;
      const row = rows.find((r) => r.object_view_id === this.objectViewId);
      if (!row || typeof row.object_data !== "string") {
        return null;
      }
      return JSON.parse(row.object_data) as LoggerState;
    } catch {
      return null;
    }
  }

  private async _isStatePersisted(): Promise<boolean> {
    const persisted = await this._fetchStateFromSelectAll();
    if (!persisted || persisted.object_view_id !== this.objectViewId) {
      return false;
    }

    const expectedLast = this.logObjects[this.logObjects.length - 1];
    if (!expectedLast) {
      return true;
    }

    return (
      persisted.logObjects?.some((entry) => entry.id === expectedLast.id) ??
      false
    );
  }
}
