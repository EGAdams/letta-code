import { describe, expect, test } from "bun:test";
import { diffNavTabs } from "../abstract/nav-live-sync.js";

describe("diffNavTabs", () => {
  test("a brand-new tab is added", () => {
    const { toAdd, toRemove } = diffNavTabs(
      ["notes", "status"],
      [
        { target: "terminal", label: "Terminal" },
        { target: "notes", label: "NOTES" },
        { target: "status", label: "System Status" },
      ],
    );
    expect(toAdd).toEqual([{ target: "terminal", label: "Terminal" }]);
    expect(toRemove).toEqual([]);
  });

  test("a removed tab is reported, and nothing else changes", () => {
    const { toAdd, toRemove } = diffNavTabs(
      ["notes", "status", "debugger"],
      [
        { target: "notes", label: "NOTES" },
        { target: "status", label: "System Status" },
      ],
    );
    expect(toAdd).toEqual([]);
    expect(toRemove).toEqual(["debugger"]);
  });

  test("an unchanged sidebar reports no diff", () => {
    const { toAdd, toRemove } = diffNavTabs(
      ["notes", "status"],
      [
        { target: "notes", label: "NOTES" },
        { target: "status", label: "System Status" },
      ],
    );
    expect(toAdd).toEqual([]);
    expect(toRemove).toEqual([]);
  });

  test("a tab already present is never re-added", () => {
    const { toAdd } = diffNavTabs(
      ["terminal"],
      [{ target: "terminal", label: "Terminal" }],
    );
    expect(toAdd).toEqual([]);
  });
});
