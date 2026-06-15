import { describe, expect, test } from "bun:test";
import { TabFactory } from "../abstract/tab-factory.interface.js";

/** Minimal element double — a real DOM element would satisfy the same shape. */
class FakeFactory extends TabFactory {
  createElement() {
    return { type: "", className: "", textContent: "", dataset: {} };
  }
}

describe("TabFactory (Factory Method)", () => {
  test("abstract createElement throws on the base", () => {
    expect(() =>
      new TabFactory().buildAgentTab({ id: "1", name: "x" }),
    ).toThrow(/createElement\(\) is abstract/);
  });

  test("buildAgentTab sets class + agent dataset", () => {
    const el = new FakeFactory().buildAgentTab({
      id: "ag-1",
      name: "Scissari",
    });
    expect(el.type).toBe("button");
    expect(el.className).toBe("tab agent-tab");
    expect(el.textContent).toBe("Scissari");
    expect(el.dataset).toEqual({
      nav: "agents",
      agentId: "ag-1",
      agentName: "Scissari",
    });
  });

  test("buildServerTab sets class + server dataset", () => {
    const el = new FakeFactory().buildServerTab({
      key: "executor",
      name: "Executor",
    });
    expect(el.className).toBe("tab");
    expect(el.textContent).toBe("Executor");
    expect(el.dataset).toEqual({
      serverKey: "executor",
      serverName: "Executor",
    });
  });

  test("buildConnectionTab sets class + connection dataset", () => {
    const el = new FakeFactory().buildConnectionTab({
      key: "win10",
      name: "Win10 Host",
    });
    expect(el.className).toBe("tab");
    expect(el.textContent).toBe("Win10 Host");
    expect(el.dataset).toEqual({
      connKey: "win10",
      connName: "Win10 Host",
    });
  });
});
