import { describe, expect, test } from "bun:test";
import { applyDeepLink } from "../boot/deep-link.js";

function fakes() {
  const calls = [];
  const cls = (name) => ({
    add: (c) => calls.push(`${name}+${c}`),
    remove: (c) => calls.push(`${name}-${c}`),
  });
  const doc = {
    querySelector: (sel) => {
      calls.push(`query ${sel}`);
      return sel.includes('data-target="terminal"')
        ? { click: () => calls.push("click terminal") }
        : null;
    },
  };
  const nav = {
    main: { classList: cls("main") },
    rolFinanceReports: { classList: cls("rf") },
  };
  const AM = { openById: (id, v) => calls.push(`agent ${id} ${v}`) };
  const RF = {
    openReports: () => {
      calls.push("reports");
      return Promise.resolve();
    },
    refreshStatus: () => {},
  };
  return { calls, doc, nav, AM, RF };
}

describe("applyDeepLink", () => {
  test("?view=terminal clicks the Terminal main-nav tab", () => {
    const f = fakes();
    applyDeepLink({ ...f, search: "?view=terminal" });
    expect(f.calls).toContain("click terminal");
  });

  test("?agent= still opens the agent view, not a main tab", () => {
    const f = fakes();
    applyDeepLink({ ...f, search: "?agent=a1&view=messages" });
    expect(f.calls).toEqual(["agent a1 messages"]);
  });

  test("?view=rol-finance-reports still opens reports", () => {
    const f = fakes();
    applyDeepLink({ ...f, search: "?view=rol-finance-reports" });
    expect(f.calls).toContain("reports");
    expect(f.calls).not.toContain("click terminal");
  });

  test("unknown or missing view does nothing", () => {
    for (const search of ["", "?view=bogus"]) {
      const f = fakes();
      applyDeepLink({ ...f, search });
      expect(f.calls).toEqual([]);
    }
  });
});
