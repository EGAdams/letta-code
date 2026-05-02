/*
 * Logger Interfaces to program to.
 */
const BASE_URL =
  process.env.LETTA_LOGGER_API ??
  "http://100.80.49.10:8284/libraries/local-php-api";

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
const PASS_COLOR = "lightgreen";
const FAIL_COLOR = "#fb6666";
const MAX_LOG_ENTRIES = 120;
const MAX_MESSAGE_CHARS = 800;
const MAX_OBJECT_DATA_BYTES = 200_000;

function defaultLed(): MonitorLed {
  return {
    classObject: {
      background_color: RUNNING_COLOR,
      text_align: "left",
      margin_top: "2px",
      color: "black",
    },
    ledText: "ready.",
    RUNNING_COLOR,
    PASS_COLOR,
    FAIL_COLOR,
  };
}

function updatedLed(message: string, current: MonitorLed): MonitorLed {
  const led: MonitorLed = {
    ...current,
    classObject: {
      ...defaultLed().classObject,
      ...(current.classObject ?? {}),
    },
    ledText: message,
  };
  // Keep compatibility with viewer semantics while also reflecting common test messages.
  // PASS: "finished", explicit PASS markers, or "test complete".
  // FAIL: explicit ERROR/FAIL markers and timeout/hang indicators.
  const isTimeoutLike =
    /timed?\s*out/i.test(message) ||
    /\btimeout\b/i.test(message) ||
    /\bhung\b/i.test(message) ||
    /\babort(?:ed|error)?\b/i.test(message);
  if (
    message.includes("finished") ||
    /\bPASS(?:ED)?\b/.test(message) ||
    /test complete/i.test(message)
  ) {
    led.classObject.background_color = PASS_COLOR;
    led.classObject.color = "black";
  } else if (
    message.includes("ERROR") ||
    /\bFAIL(?:ED)?\b/.test(message) ||
    isTimeoutLike
  ) {
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
    this.monitorLed = defaultLed();
  }

  private _shouldSoftFail(err: unknown): boolean {
    if (process.env.LETTA_LOGGER_OPTIONAL !== "1") return false;
    const msg = err instanceof Error ? err.message : String(err);
    return /HTTP\s+(503|507)\b/i.test(msg);
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
    const rand = Math.floor(Math.random() * 1e13);
    const safeMessage =
      typeof message === "string"
        ? message.slice(0, MAX_MESSAGE_CHARS)
        : String(message).slice(0, MAX_MESSAGE_CHARS);
    this.logObjects.push({
      timestamp,
      id: `${this.objectViewId}_${rand}_${timestamp}`,
      message: safeMessage,
      method: "createLogObject",
    });
    this._shrinkStateForTransport();
    this.monitorLed = updatedLed(safeMessage, this.monitorLed);
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
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      await fetch(`${BASE_URL}/object/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ object_view_id: this.objectViewId }),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timer);
    }
  }

  private _state(): LoggerState {
    return {
      object_view_id: this.objectViewId,
      logObjects: this.logObjects,
      monitorLed: this.monitorLed,
    };
  }

  private _serializedState(): string {
    this._shrinkStateForTransport();
    return JSON.stringify(this._state());
  }

  private _shrinkStateForTransport(): void {
    if (this.logObjects.length > MAX_LOG_ENTRIES) {
      this.logObjects = this.logObjects.slice(-MAX_LOG_ENTRIES);
    }

    // Enforce a hard ceiling on outgoing object_data bytes.
    // Keep newest entries and drop oldest until payload is within bound.
    let serialized = JSON.stringify(this._state());
    while (
      serialized.length > MAX_OBJECT_DATA_BYTES &&
      this.logObjects.length > 1
    ) {
      this.logObjects.shift();
      serialized = JSON.stringify(this._state());
    }
  }

  private async _post(
    action: "insert" | "update",
    timeoutMs = 8000,
  ): Promise<void> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let res: Response;
    try {
      res = await fetch(`${BASE_URL}/object/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          object_view_id: this.objectViewId,
          object_data: this._serializedState(),
        }),
        signal: controller.signal,
      });
    } catch (err) {
      clearTimeout(timer);
      if (await this._isStatePersisted()) {
        return;
      }
      if (this._shouldSoftFail(err)) {
        return;
      }
      throw new Error(
        `[RemoteLogger] ${action} failed before response: ${err instanceof Error ? err.message : String(err)}`,
      );
    }

    clearTimeout(timer);

    if (!res.ok) {
      if (action === "update" && (await this._tryInsertFallback())) {
        return;
      }
      // The production API can occasionally return HTTP 500 while still persisting.
      if (await this._isStatePersistedWithRetry()) {
        return;
      }
      const httpErr = new Error(
        `[RemoteLogger] ${action} failed (HTTP ${res.status})`,
      );
      if (this._shouldSoftFail(httpErr)) {
        return;
      }
      throw httpErr;
    }

    let body: unknown;
    try {
      body = (await res.json()) as unknown;
    } catch {
      if (await this._isStatePersistedWithRetry()) {
        return;
      }
      const jsonErr = new Error(
        `[RemoteLogger] ${action} failed (invalid JSON response)`,
      );
      if (this._shouldSoftFail(jsonErr)) {
        return;
      }
      throw jsonErr;
    }

    if (
      body !== null &&
      typeof body === "object" &&
      (body as Record<string, unknown>)["error"]
    ) {
      if (action === "update" && (await this._tryInsertFallback())) {
        return;
      }
      if (await this._isStatePersistedWithRetry()) {
        return;
      }
      const bodyErr = new Error(
        `[RemoteLogger] ${action} error: ${JSON.stringify(body)}`,
      );
      if (this._shouldSoftFail(bodyErr)) {
        return;
      }
      throw bodyErr;
    }
  }

  private async _tryInsertFallback(): Promise<boolean> {
    try {
      const ac = new AbortController();
      const t = setTimeout(() => ac.abort(), 8000);
      const insertRes = await fetch(`${BASE_URL}/object/insert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          object_view_id: this.objectViewId,
          object_data: this._serializedState(),
        }),
        signal: ac.signal,
      });
      clearTimeout(t);
      if (!insertRes.ok) {
        return false;
      }
      return this._isStatePersisted();
    } catch {
      return false;
    }
  }

  private async _fetchExistingState(): Promise<LoggerState | null> {
    try {
      const ac = new AbortController();
      const t = setTimeout(() => ac.abort(), 8000);
      const res = await fetch(
        `${BASE_URL}/object/select?object_view_id=${encodeURIComponent(this.objectViewId)}`,
        { signal: ac.signal },
      );
      clearTimeout(t);
      if (res.ok) {
        const data = (await res.json()) as Record<string, unknown> | null;
        const parsed = this._parseSelectPayload(data);
        if (parsed) {
          return parsed;
        }
      }
    } catch {
      return null;
    }
    return null;
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

  private async _isStatePersisted(): Promise<boolean> {
    const persisted = await this._fetchExistingState();
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

  private async _isStatePersistedWithRetry(
    attempts = 4,
    delayMs = 250,
  ): Promise<boolean> {
    for (let i = 0; i < attempts; i += 1) {
      if (await this._isStatePersisted()) {
        return true;
      }
      if (i < attempts - 1) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }
    return false;
  }
}
