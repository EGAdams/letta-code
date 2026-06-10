import { beforeEach, describe, expect, test } from "bun:test";
import { ConsoleView } from "../abstract/console-view.interface.js";

/** String-buffer console: no DOM, records writes + scrolls. */
class BufferConsole extends ConsoleView {
  constructor() {
    super();
    this.buffer = "";
    this.scrolls = 0;
  }
  writeHtml(html) {
    this.buffer += html;
  }
  replaceHtml(html) {
    this.buffer = html;
  }
  scrollToBottom() {
    this.scrolls += 1;
  }
}

describe("ConsoleView (Template Method dedup)", () => {
  let c;
  beforeEach(() => {
    c = new BufferConsole();
  });

  test("abstract primitives throw on the base class", () => {
    const base = new ConsoleView();
    expect(() => base.writeHtml("x")).toThrow(/writeHtml\(\) is abstract/);
    expect(() => base.scrollToBottom()).toThrow(/scrollToBottom/);
  });

  test("first appendUnique clears placeholder then writes", () => {
    c.replaceHtml("<i>placeholder</i>");
    c.appendUnique("k1", "<div>one</div>");
    expect(c.buffer).toBe("<div>one</div>");
  });

  test("duplicate keys are skipped", () => {
    expect(c.appendUnique("k1", "<div>one</div>")).toBe(true);
    expect(c.appendUnique("k1", "<div>dup</div>")).toBe(false);
    expect(c.buffer).toBe("<div>one</div>");
  });

  test("auto-scrolls on each new row by default", () => {
    c.appendUnique("k1", "a");
    c.appendUnique("k2", "b");
    expect(c.scrolls).toBe(2);
  });

  test("autoScroll:false suppresses scroll", () => {
    c.appendUnique("k1", "a", { autoScroll: false });
    expect(c.scrolls).toBe(0);
  });

  test("renderEmptyOnce only fires on first render", () => {
    expect(c.renderEmptyOnce("<i>empty</i>")).toBe(true);
    expect(c.buffer).toBe("<i>empty</i>");
    expect(c.renderEmptyOnce("<i>again</i>")).toBe(false);
  });

  test("reset restores first-render + clears seen set", () => {
    c.appendUnique("k1", "a");
    c.reset();
    expect(c.isFirstRender).toBe(true);
    expect(c.appendUnique("k1", "fresh")).toBe(true); // key no longer seen
  });
});
