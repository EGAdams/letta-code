import { describe, expect, test } from "bun:test";
import { DomTabFactory } from "../implementation/dom-tab-factory.js";
import { FakeDocument } from "./_fake-dom.js";

describe("DomTabFactory (concrete TabFactory)", () => {
  test("builds an agent tab as a configured <button>", () => {
    const doc = new FakeDocument();
    const f = new DomTabFactory(doc);
    const el = f.buildAgentTab({ id: "a1", name: "Scissari" });
    expect(el.tagName).toBe("BUTTON");
    expect(el.type).toBe("button");
    expect(el.classList.contains("tab")).toBe(true);
    expect(el.classList.contains("agent-tab")).toBe(true);
    expect(el.textContent).toBe("Scissari");
    expect(el.dataset).toEqual({
      nav: "agents",
      agentId: "a1",
      agentName: "Scissari",
    });
  });

  test("builds a server tab with server data attributes", () => {
    const doc = new FakeDocument();
    const el = new DomTabFactory(doc).buildServerTab({
      key: "executor",
      name: "Executor",
    });
    expect(el.classList.contains("tab")).toBe(true);
    expect(el.dataset).toEqual({
      serverKey: "executor",
      serverName: "Executor",
    });
  });
});
