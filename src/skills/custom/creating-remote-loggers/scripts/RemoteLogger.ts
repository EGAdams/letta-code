const BASE_URL =
  "https://americansjewelry.com/libraries/local-php-api/index.php";

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
  if (message.includes("ERROR")) {
    led.classObject.background_color = FAIL_COLOR;
    led.classObject.color = "white";
  } else if (message.includes("finished") || message.includes("PASS")) {
    led.classObject.background_color = PASS_COLOR;
    led.classObject.color = "black";
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
    const res = await fetch(
      `${BASE_URL}/object/select/${encodeURIComponent(this.objectViewId)}`,
    );
    if (res.ok) {
      const data = (await res.json()) as Record<string, unknown> | null;
      if (data && !data.error && data.object_data) {
        const state = JSON.parse(data.object_data as string) as LoggerState;
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
    // Use no-cors mode (matching FetchRunner.ts in the-factory) so the browser
    // skips the OPTIONS preflight. The response is opaque but the PHP backend
    // reads the body via file_get_contents('php://input') regardless of headers.
    await fetch(`${BASE_URL}/object/${action}`, {
      method:  "POST",
      mode:    "no-cors",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        object_view_id: this.objectViewId,
        object_data:    JSON.stringify(this._state()),
      }),
    });
  }
}
