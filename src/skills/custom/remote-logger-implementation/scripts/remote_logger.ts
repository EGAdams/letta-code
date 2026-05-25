const BASE_URL =
  process.env.LETTA_LOGGER_API ??
  "http://100.80.49.10:8284/libraries/local-php-api";

type LogEntry = {
  timestamp: number;
  id: string;
  message: string;
  method: string;
};

type MonitorLedClassObject = {
  background_color: string;
  text_align: string;
  margin_top: string;
  color: string;
};

type MonitorLed = {
  classObject: MonitorLedClassObject;
  ledText: string;
  RUNNING_COLOR: string;
  PASS_COLOR: string;
  FAIL_COLOR: string;
};

type LoggerState = {
  object_view_id: string;
  logObjects: LogEntry[];
  monitorLed: MonitorLed;
};

const RUNNING_COLOR = "lightyellow";
const PASS_COLOR = "lightgreen";
const FAIL_COLOR = "#fb6666";
const MAX_LOG_ENTRIES = 120;
const MAX_MESSAGE_CHARS = 800;
const MAX_OBJECT_DATA_BYTES = 200_000;
const ANSI_ESCAPE_PATTERN = /\u001b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g;
const SAFE_APOSTROPHE = "\u2019";
const SAFE_DOUBLE_QUOTE = "\u201d";

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

function sanitizeLogMessage(message: string): string {
  return message
    .replace(ANSI_ESCAPE_PATTERN, "")
    .replace(/'/g, SAFE_APOSTROPHE)
    .replace(/"/g, SAFE_DOUBLE_QUOTE)
    .replace(/[\r\t]+/g, " ")
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, " ")
    .replace(/ {2,}/g, " ")
    .replace(/\n+/g, " | ")
    .trim();
}

export class RemoteLogger {
  private objectViewId: string;
  private logObjects: LogEntry[] = [];
  private monitorLed: MonitorLed = defaultLed();

  constructor(objectViewId: string) {
    this.objectViewId = objectViewId;
  }

  async init(): Promise<void> {
    const existing = await this.fetchExistingState();
    if (existing) {
      this.logObjects = existing.logObjects ?? [];
      const rawLed = existing.monitorLed ?? defaultLed();
      this.monitorLed = rawLed.classObject
        ? rawLed
        : { ...rawLed, classObject: defaultLed().classObject };
      if (!existing.monitorLed?.classObject) {
        await this.post("update");
      }
      return;
    }
    await this.post("insert");
  }

  async log(message: string): Promise<void> {
    const safeMessage = sanitizeLogMessage(
      String(message).slice(0, MAX_MESSAGE_CHARS),
    );
    const timestamp = Date.now();
    const rand = Math.floor(Math.random() * 1e13);

    this.logObjects.push({
      timestamp,
      id: `${this.objectViewId}_${rand}_${timestamp}`,
      message: safeMessage,
      method: "createLogObject",
    });

    this.shrinkStateForTransport();
    this.monitorLed = updatedLed(safeMessage, this.monitorLed);
    await this.post("update");
  }

  async clearLogs(ledText = "ready."): Promise<void> {
    this.monitorLed = { ...defaultLed(), ledText };
    await this.post("update");
  }

  async flushLogs(ledText = "ready."): Promise<void> {
    this.logObjects = [];
    this.monitorLed = { ...defaultLed(), ledText };
    await this.post("update");
  }

  private state(): LoggerState {
    return {
      object_view_id: this.objectViewId,
      logObjects: this.logObjects,
      monitorLed: this.monitorLed,
    };
  }

  private serializedState(): string {
    this.shrinkStateForTransport();
    return JSON.stringify(this.state());
  }

  private shrinkStateForTransport(): void {
    if (this.logObjects.length > MAX_LOG_ENTRIES) {
      this.logObjects = this.logObjects.slice(-MAX_LOG_ENTRIES);
    }

    let serialized = JSON.stringify(this.state());
    while (
      serialized.length > MAX_OBJECT_DATA_BYTES &&
      this.logObjects.length > 1
    ) {
      this.logObjects.shift();
      serialized = JSON.stringify(this.state());
    }
  }

  private async post(
    action: "insert" | "update",
    timeoutMs = 8000,
  ): Promise<void> {
    const payload = {
      object_view_id: this.objectViewId,
      object_data: this.serializedState(),
    };

    let res: Response;
    try {
      res = await fetchWithTimeout(
        `${BASE_URL}/object/${action}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
        timeoutMs,
      );
    } catch (err) {
      if (await this.isStatePersisted()) return;
      throw new Error(
        `[RemoteLogger] ${action} failed before response: ${err instanceof Error ? err.message : String(err)}`,
      );
    }

    if (!res.ok) {
      if (action === "update" && (await this.tryInsertFallback(timeoutMs)))
        return;
      if (await this.isStatePersistedWithRetry()) return;
      throw new Error(`[RemoteLogger] ${action} failed (HTTP ${res.status})`);
    }

    try {
      const body = (await res.json()) as Record<string, unknown> | null;
      if (body?.error) {
        if (action === "update" && (await this.tryInsertFallback(timeoutMs)))
          return;
        if (await this.isStatePersistedWithRetry()) return;
        throw new Error(
          `[RemoteLogger] ${action} error: ${JSON.stringify(body)}`,
        );
      }
    } catch (err) {
      if (await this.isStatePersistedWithRetry()) return;
      throw new Error(
        `[RemoteLogger] ${action} failed (invalid JSON response): ${err instanceof Error ? err.message : String(err)}`,
      );
    }
  }

  private async tryInsertFallback(timeoutMs = 8000): Promise<boolean> {
    try {
      const res = await fetchWithTimeout(
        `${BASE_URL}/object/insert`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            object_view_id: this.objectViewId,
            object_data: this.serializedState(),
          }),
        },
        timeoutMs,
      );
      if (!res.ok) return false;
      return this.isStatePersisted();
    } catch {
      return false;
    }
  }

  private async fetchExistingState(): Promise<LoggerState | null> {
    try {
      const res = await fetchWithTimeout(
        `${BASE_URL}/object/select?object_view_id=${encodeURIComponent(this.objectViewId)}`,
        { method: "GET" },
        8000,
      );
      if (!res.ok) return null;
      const data = (await res.json()) as Record<string, unknown> | null;
      return this.parseSelectPayload(data);
    } catch {
      return null;
    }
  }

  private parseSelectPayload(
    data: Record<string, unknown> | null,
  ): LoggerState | null {
    if (!data || data.error || !data.object_data) return null;
    try {
      return JSON.parse(data.object_data as string) as LoggerState;
    } catch {
      return null;
    }
  }

  private async isStatePersisted(): Promise<boolean> {
    const persisted = await this.fetchExistingState();
    if (!persisted || persisted.object_view_id !== this.objectViewId)
      return false;

    const expectedLast = this.logObjects[this.logObjects.length - 1];
    if (!expectedLast) return true;

    return (
      persisted.logObjects?.some((entry) => entry.id === expectedLast.id) ??
      false
    );
  }

  private async isStatePersistedWithRetry(
    attempts = 4,
    delayMs = 250,
  ): Promise<boolean> {
    for (let i = 0; i < attempts; i += 1) {
      if (await this.isStatePersisted()) return true;
      if (i < attempts - 1) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }
    return false;
  }
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: ac.signal });
  } finally {
    clearTimeout(t);
  }
}
