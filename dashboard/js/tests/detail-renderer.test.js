import { describe, expect, test } from "bun:test";
import {
  DetailRenderer,
  DetailRendererRegistry,
} from "../abstract/detail-renderer.interface.js";

class SpyRenderer extends DetailRenderer {
  constructor() {
    super();
    this.calls = [];
  }
  render(target, agentId) {
    this.calls.push({ target, agentId });
  }
}

describe("DetailRenderer (Strategy)", () => {
  test("abstract render throws", () => {
    expect(() => new DetailRenderer().render("t", "a")).toThrow(
      /render\(\) is abstract/,
    );
  });
});

describe("DetailRendererRegistry (Context)", () => {
  test("register rejects non-DetailRenderer strategies", () => {
    const reg = new DetailRendererRegistry();
    expect(() => reg.register("x", { render() {} })).toThrow(TypeError);
  });

  test("dispatches to the registered strategy", () => {
    const reg = new DetailRendererRegistry();
    const thoughts = new SpyRenderer();
    reg.register("agent-detail-thoughts", thoughts);
    expect(reg.has("agent-detail-thoughts")).toBe(true);

    const handled = reg.render("agent-detail-thoughts", "#el", "agent-1");
    expect(handled).toBe(true);
    expect(thoughts.calls).toEqual([{ target: "#el", agentId: "agent-1" }]);
  });

  test("unknown view id is a silent no-op", () => {
    const reg = new DetailRendererRegistry();
    expect(reg.render("nope", "#el", "a")).toBe(false);
  });

  test("register is chainable", () => {
    const reg = new DetailRendererRegistry();
    const out = reg
      .register("a", new SpyRenderer())
      .register("b", new SpyRenderer());
    expect(out).toBe(reg);
    expect(reg.has("b")).toBe(true);
  });
});
