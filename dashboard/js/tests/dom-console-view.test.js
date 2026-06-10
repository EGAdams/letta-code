import { describe, expect, test } from "bun:test";
import { DomConsoleView } from "../implementation/dom-console-view.js";
import { FakeDocument } from "./_fake-dom.js";

describe("DomConsoleView (concrete ConsoleView)", () => {
  test("requires a box with a .msi-inner child", () => {
    expect(() => new DomConsoleView(null)).toThrow(/requires a console box/);
  });

  test("binds primitives to the DOM and inherits dedup", () => {
    const doc = new FakeDocument();
    const box = doc.createElement("div");
    const inner = doc.createElement("span");
    inner.className = "msi-inner";
    box.appendChild(inner);
    box.scrollHeight = 500;

    const view = new DomConsoleView(box);
    view.appendUnique("k1", "<div>one</div>");
    view.appendUnique("k1", "<div>dup</div>"); // deduped
    view.appendUnique("k2", "<div>two</div>");

    expect(inner.innerHTML).toBe("<div>one</div><div>two</div>");
    expect(box.scrollTop).toBe(500); // scrolled to bottom
  });

  test("mount() builds a queryable shell and returns a bound view", () => {
    const doc = new FakeDocument();
    const container = doc.createElement("section");
    const view = DomConsoleView.mount(container, "thoughts", doc);

    const box = container.querySelector(".msi-console");
    expect(box).not.toBeNull();
    expect(box.id).toBe("msi-thoughts");
    expect(box.querySelector(".msi-inner")).not.toBeNull();

    view.appendUnique("k", "<div>row</div>");
    expect(box.querySelector(".msi-inner").innerHTML).toBe("<div>row</div>");
  });
});
