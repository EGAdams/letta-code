import { describe, expect, test } from "bun:test";
import {
  needsAction,
  reconciliationState,
  renderMazdaToolReconciliation,
} from "../abstract/mazda-tool-reconciliation.js";

const agreed = {
  ok: true,
  reachable: true,
  agent_id: "agent-6b53",
  base_url: "http://letta:8283",
  served: ["record_trace", "judge_trace"],
  attached: ["record_trace", "judge_trace", "run_claude_code_sdk"],
  other_attached: ["run_claude_code_sdk"],
  missing: [],
  stale: [],
  remediation: "python -m ...registry",
};

describe("reconciliationState", () => {
  test("agreed when nothing is missing or stale", () => {
    expect(reconciliationState(agreed)).toBe("agreed");
    expect(needsAction(agreed)).toBe(false);
  });

  test("missing outranks stale — an uncallable tool is the worse fault", () => {
    const d = { ...agreed, missing: ["record_trace"], stale: ["old_tool"] };
    expect(reconciliationState(d)).toBe("missing");
    expect(needsAction(d)).toBe(true);
  });

  test("stale on its own is still an action", () => {
    expect(needsAction({ ...agreed, stale: ["old_tool"] })).toBe(true);
  });

  test("an unreachable server is its own state, not a false green", () => {
    expect(reconciliationState({ reachable: false })).toBe("unreachable");
    expect(reconciliationState(null)).toBe("unreachable");
  });
});

describe("renderMazdaToolReconciliation", () => {
  test("green panel still lists what it checked", () => {
    const h = renderMazdaToolReconciliation(agreed);
    expect(h).toContain("mtr-ok");
    expect(h).toContain("in sync");
    expect(h).toContain("record_trace");
    expect(h).toContain("Nothing to run");
  });

  test("missing tools are named and the fix command is shown", () => {
    const h = renderMazdaToolReconciliation({
      ...agreed,
      missing: ["record_trace"],
    });
    expect(h).toContain("mtr-bad");
    expect(h).toContain("record_trace");
    expect(h).toContain("python -m ...registry");
  });

  test("stale tools render amber, not red", () => {
    const h = renderMazdaToolReconciliation({ ...agreed, stale: ["old_tool"] });
    expect(h).toContain("mtr-warn");
    expect(h).not.toContain("mtr-bad");
    expect(h).toContain("old_tool");
  });

  test("tools from other MCP servers are context, never a fault", () => {
    const h = renderMazdaToolReconciliation(agreed);
    expect(h).toContain("run_claude_code_sdk");
    expect(h).toContain("not part of this");
  });

  test("an unreachable server never renders a green card", () => {
    const h = renderMazdaToolReconciliation({
      reachable: false,
      text: "connection refused",
    });
    expect(h).toContain("mtr-bad");
    expect(h).toContain("connection refused");
    // The verdict lives in the card class, not the prose — assert on that.
    expect(h).not.toContain("mtr-ok");
  });

  test("escapes tool names rather than injecting them as markup", () => {
    const h = renderMazdaToolReconciliation({
      ...agreed,
      missing: ["<img src=x onerror=alert(1)>"],
    });
    expect(h).not.toContain("<img");
    expect(h).toContain("&lt;img");
  });
});

test("unreachable card defaults to blaming the Letta server", () => {
  const h = renderMazdaToolReconciliation({
    reachable: false,
    text: "timeout",
  });
  expect(h).toContain("Letta server");
});

test("a caller-supplied hint replaces the default, so a 404 does not accuse Letta", () => {
  // The dashboard 404ing its own route is a stale-build problem on *this*
  // host. The panel must point there, not at Letta.
  const h = renderMazdaToolReconciliation({
    reachable: false,
    text: "Reconciliation check failed: HTTP 404",
    hint: "Restart dashboard-server.service.",
  });
  expect(h).toContain("Restart dashboard-server.service.");
  expect(h).not.toContain("Letta server");
});

test("the hint is escaped like every other untrusted string", () => {
  const h = renderMazdaToolReconciliation({
    reachable: false,
    text: "x",
    hint: "<img src=x onerror=alert(1)>",
  });
  expect(h).toContain("&lt;img");
  expect(h).not.toContain("<img src=x");
});
