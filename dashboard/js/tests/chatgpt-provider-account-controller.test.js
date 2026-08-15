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
    super(deps);
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
});
