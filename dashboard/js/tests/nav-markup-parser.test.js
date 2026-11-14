import { describe, expect, test } from "bun:test";
import {
  parseNavMainMarkup,
  parseNavMainTabs,
  parseViewSection,
} from "../abstract/nav-markup-parser.js";

const PAGE = `<!doctype html><html><body>
  <nav id="nav-main">
    <button type="button" class="tab" data-nav="main" data-target="terminal">Terminal</button>
    <button type="button" class="tab" data-nav="main" data-target="notes">NOTES</button>
    <button type="button" class="tab" data-nav="main" data-target="status" id="btn-system-status">System Status</button>
    <button type="button" class="tab" data-nav="main" data-target="debugger">Debugger</button>
  </nav>
  <nav id="nav-debugger" class="hidden">
    <button type="button" class="tab" data-nav="debugger" data-target="debugger-adw-parent">ADW Parent</button>
  </nav>
  <section id="terminal" class="view">
    <h2>Terminal</h2>
    <p>Placeholder — no command execution wired up yet.</p>
  </section>
  <section id="debugger-adw-parent" class="view"><h2>ADW Parent</h2></section>
</body></html>`;

describe("parseNavMainMarkup", () => {
  test("extracts only the nav-main block", () => {
    const inner = parseNavMainMarkup(PAGE);
    expect(inner).toContain('data-target="terminal"');
    expect(inner).not.toContain("debugger-adw-parent");
  });

  test("returns empty string when there is no nav-main", () => {
    expect(parseNavMainMarkup("<html></html>")).toBe("");
  });
});

describe("parseNavMainTabs", () => {
  test("returns every top-level tab in document order", () => {
    const tabs = parseNavMainTabs(PAGE);
    expect(tabs.map((t) => t.target)).toEqual([
      "terminal",
      "notes",
      "status",
      "debugger",
    ]);
  });

  test("strips nested markup and trims the label", () => {
    const tabs = parseNavMainTabs(PAGE);
    expect(tabs.find((t) => t.target === "terminal").label).toBe("Terminal");
  });

  test("ignores buttons from a different nav", () => {
    const tabs = parseNavMainTabs(PAGE);
    expect(tabs.some((t) => t.target === "debugger-adw-parent")).toBe(false);
  });

  test("deduplicates a repeated data-target, keeping the first", () => {
    const html = `<nav id="nav-main">
      <button data-nav="main" data-target="x">First</button>
      <button data-nav="main" data-target="x">Second</button>
    </nav>`;
    expect(parseNavMainTabs(html)).toEqual([{ target: "x", label: "First" }]);
  });
});

describe("parseViewSection", () => {
  test("returns the matching section's id/class/innerHTML", () => {
    const section = parseViewSection(PAGE, "terminal");
    expect(section.id).toBe("terminal");
    expect(section.className).toBe("view");
    expect(section.innerHTML).toContain("<h2>Terminal</h2>");
  });

  test("returns null when the target has no section", () => {
    expect(parseViewSection(PAGE, "nope")).toBeNull();
  });
});
