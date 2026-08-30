import { describe, expect, test } from "bun:test";
import { ChatGptProviderAccountController } from "../abstract/chatgpt-provider-account-controller.interface.js";
import {
  assertChatGptProviderAccountStatus,
  renderChatGptProviderAccountPanel,
} from "../abstract/chatgpt-provider-account-status.js";

const STATUS = {
  active_email: "eg1972@gmail.com",
  sources: [
    { key: "w11", label: "EG's account (W11)" },
    { key: "r46", label: "Mom's account (R46)" },
  ],
  ran: false,
  ok: null,
  text: null,
  source: null,
  provider_token_state: "valid",
  provider_expires_at: 1_800_000_000,
  local_token_state: "valid",
  local_expires_at: 1_800_000_100,
  sync_recommended: false,
  token_status_detail: "",
  incident_id: "incident-valid",
};

const fakeHttp = (getResult, postResult) => {
  const calls = [];
  return {
    calls,
    getJSON: async (url) => {
      calls.push({ method: "GET", url });
      if (getResult instanceof Error) throw getResult;
      return getResult;
    },
    postJSON: async (url, body) => {
      calls.push({ method: "POST", url, body });
      if (postResult instanceof Error) throw postResult;
      return postResult;
    },
  };
};

// Minimal fake DOM: id -> element, tracking innerHTML/click listeners.
class FakeElement {
  constructor() {
    this.innerHTML = "";
    this.disabled = false;
    this.textContent = "";
    this._listeners = {};
    const classes = new Set(["hidden"]);
    this.classList = {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
      contains: (name) => classes.has(name),
      toggle: (name, force) => {
        if (force) classes.add(name);
        else classes.delete(name);
      },
    };
  }
  addEventListener(type, fn) {
    this._listeners[type] = fn;
  }
  click() {
    this._listeners.click?.();
  }
}

class TestController extends ChatGptProviderAccountController {
  constructor(deps) {
    super({ ...deps, setInterval: () => 1 });
    this._elements = { panel: new FakeElement() };
  }
  _getElement(id) {
    if (id === "panel") return this._elements.panel;
    // buttons are looked up by id after render; register lazily
    this._elements[id] ??= new FakeElement();
    return this._elements[id];
  }
}

describe("assertChatGptProviderAccountStatus", () => {
  test("accepts a well-formed payload", () => {
    expect(assertChatGptProviderAccountStatus(STATUS)).toEqual(STATUS);
  });

  test("rejects a non-array sources field", () => {
    expect(() =>
      assertChatGptProviderAccountStatus({ sources: "nope" }),
    ).toThrow(TypeError);
  });
});

describe("renderChatGptProviderAccountPanel", () => {
  test("shows the active email and a button per source", () => {
    const html = renderChatGptProviderAccountPanel(STATUS);
    expect(html).toContain("eg1972@gmail.com");
    expect(html).toContain('id="cgpa-set-w11-btn"');
    expect(html).toContain('id="cgpa-set-r46-btn"');
  });
});

describe("ChatGptProviderAccountController (Template Method)", () => {
  test("validates the http port", () => {
    expect(() => new ChatGptProviderAccountController({})).toThrow(/requires/);
  });

  test("binds the browser timer so mount does not throw Illegal invocation", () => {
    const originalSetInterval = globalThis.setInterval;
    let timerReceiver = null;
    globalThis.setInterval = function () {
      timerReceiver = this;
      return 1;
    };
    try {
      const http = fakeHttp(STATUS);
      class BrowserTimerController extends ChatGptProviderAccountController {
        _getElement() {
          return null;
        }
      }
      const c = new BrowserTimerController({ http });
      c.mount("panel");
      expect(timerReceiver).toBe(globalThis);
    } finally {
      globalThis.setInterval = originalSetInterval;
    }
  });

  test("mount() fetches status and renders into the container", async () => {
    const http = fakeHttp(STATUS);
    const c = new TestController({ http });

    c.mount("panel");
    await Promise.resolve();
    await Promise.resolve();

    expect(http.calls[0]).toEqual({
      method: "GET",
      url: "/api/chatgpt-provider-account-status",
    });
    expect(c._elements.panel.innerHTML).toContain("eg1972@gmail.com");
  });

  test("setAccount() POSTs the chosen source and re-renders on success", async () => {
    const swapped = {
      ...STATUS,
      active_email: "rbarnesrol@aol.com",
      ran: true,
      ok: true,
      source: "r46",
    };
    const http = fakeHttp(STATUS, swapped);
    const c = new TestController({ http });
    c.mount("panel");
    await Promise.resolve();
    await Promise.resolve();

    await c.setAccount("r46");

    expect(http.calls[1]).toEqual({
      method: "POST",
      url: "/api/chatgpt-provider-account",
      body: { source: "r46" },
    });
    expect(c._elements.panel.innerHTML).toContain("rbarnesrol@aol.com");
  });

  test("setAccount() surfaces a failed swap without throwing", async () => {
    const http = fakeHttp(STATUS, new Error("swap failed: dead token"));
    const c = new TestController({ http });
    c.mount("panel");
    await Promise.resolve();
    await Promise.resolve();

    await c.setAccount("w11");

    expect(c._status.ok).toBe(false);
    expect(c._status.text).toBe("swap failed: dead token");
  });

  test("expired provider opens the sync dialog once and No dismisses that incident", async () => {
    const expired = {
      ...STATUS,
      provider_token_state: "expired",
      sync_recommended: true,
      token_status_detail: "Letta provider token expired",
      incident_id: "expired-copy-1",
    };
    const http = fakeHttp(expired);
    const c = new TestController({ http });

    c.mount("panel");
    await Promise.resolve();
    await Promise.resolve();
    const modal = c._elements["provider-token-sync-modal"];
    expect(modal.classList.contains("hidden")).toBe(false);

    c._elements["provider-token-sync-no"].click();
    expect(modal.classList.contains("hidden")).toBe(true);
    await c.refresh();
    expect(modal.classList.contains("hidden")).toBe(true);
  });

  test("Yes synchronizes from W11 and closes the dialog", async () => {
    const expired = {
      ...STATUS,
      provider_token_state: "expired",
      sync_recommended: true,
      incident_id: "expired-copy-2",
    };
    const http = fakeHttp(expired, STATUS);
    const c = new TestController({ http });
    c.mount("panel");
    await Promise.resolve();
    await Promise.resolve();

    c._elements["provider-token-sync-yes"].click();
    await Promise.resolve();
    await Promise.resolve();

    expect(http.calls).toContainEqual({
      method: "POST",
      url: "/api/chatgpt-provider-account",
      body: { source: "w11" },
    });
    expect(
      c._elements["provider-token-sync-modal"].classList.contains("hidden"),
    ).toBe(true);
  });
});
