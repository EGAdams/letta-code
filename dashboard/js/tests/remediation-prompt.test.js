import { describe, expect, test } from "bun:test";
import {
  buildRemediationPrompt,
  extractPaths,
  redactSecrets,
} from "../abstract/remediation-prompt.js";

describe("redactSecrets", () => {
  test("masks key/token/secret/password-shaped pairs", () => {
    expect(redactSecrets("api_key: sk-abcdefghijklmnop")).toBe("[REDACTED]");
    expect(redactSecrets('password="hunter2hunter2"')).toBe("[REDACTED]");
    expect(redactSecrets("Authorization: Bearer abc.def.ghi")).toContain(
      "[REDACTED]",
    );
  });

  test("masks bare bearer tokens, sk- keys, AWS keys and JWTs even without a label", () => {
    expect(redactSecrets("saw Bearer abcDEF123.456-token in the log")).toBe(
      "saw [REDACTED] in the log",
    );
    expect(redactSecrets("key=sk-abcdefghijklmnop1234")).toBe("[REDACTED]");
    expect(redactSecrets("AKIAABCDEFGHIJKLMNOP leaked")).toBe(
      "[REDACTED] leaked",
    );
    expect(
      redactSecrets("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123"),
    ).toBe("[REDACTED]");
  });

  test("leaves ordinary error text untouched", () => {
    const text =
      "TypeError: cannot read properties of undefined (reading 'id')";
    expect(redactSecrets(text)).toBe(text);
  });
});

describe("extractPaths", () => {
  test("finds file:line references and plain paths, de-duplicated", () => {
    const text =
      'at dashboard/server.py:142\n  File "dashboard/server.py", line 142\n  see js/boot/worker-activity.js too';
    expect(extractPaths(text)).toEqual([
      "dashboard/server.py:142",
      "js/boot/worker-activity.js",
    ]);
  });

  test("reports nothing found rather than guessing", () => {
    expect(extractPaths("a plain message with no paths in it")).toEqual([]);
  });
});

describe("buildRemediationPrompt", () => {
  const alert = {
    title: "ADW supervisor: task t_2 failed (URGENT)",
    text: "The task ended failed. See dashboard/adw_task_alerts.py:93 for the row builder.",
    agent: "adw_tasks",
    severity: "urgent",
    outcome: "",
    ids: ["t_2"],
    sources: [],
  };

  test("includes the exact error, timestamp, host, agent and task id", () => {
    const prompt = buildRemediationPrompt(alert, {
      generatedAt: "2026-11-21T00:00:00.000Z",
      host: "DESKTOP-2OBSQMC",
    });
    expect(prompt).toContain("## Exact error");
    expect(prompt).toContain("The task ended failed.");
    expect(prompt).toContain("Timestamp: 2026-11-21T00:00:00.000Z");
    expect(prompt).toContain("Host: DESKTOP-2OBSQMC");
    expect(prompt).toContain("Agent: adw_tasks");
    expect(prompt).toContain("Task ID(s): t_2");
  });

  test("lists detected file paths and a reproduction, expected-vs-actual and acceptance tests", () => {
    const prompt = buildRemediationPrompt(alert, {
      generatedAt: "now",
      host: "h",
    });
    expect(prompt).toContain("dashboard/adw_task_alerts.py:93");
    expect(prompt).toContain("## Reproduction");
    expect(prompt).toContain("## Expected vs actual");
    expect(prompt).toContain("## Acceptance tests");
    expect(prompt).toContain("- [ ]");
  });

  test("never puts a raw secret from the alert text into the prompt", () => {
    const leaky = {
      ...alert,
      text: "upstream call failed: Authorization: Bearer sk-liveSECRETVALUE123",
    };
    const prompt = buildRemediationPrompt(leaky, {
      generatedAt: "now",
      host: "h",
    });
    expect(prompt).not.toContain("sk-liveSECRETVALUE123");
    expect(prompt).toContain("[REDACTED]");
    expect(prompt).toContain("## Secrets");
  });

  test("says plainly when no paths or error text were reported, instead of inventing them", () => {
    const prompt = buildRemediationPrompt(
      { agent: "x", ids: [] },
      { generatedAt: "now", host: "h" },
    );
    expect(prompt).toContain("None detected in the alert text.");
    expect(prompt).toContain("(no error text was reported)");
    expect(prompt).toContain("Task ID(s): none reported");
  });
});

describe("a Star Trek Bridge gateway alert", () => {
  test("gets follow-through steps, not a re-run-and-add-a-test bug report", () => {
    const out = buildRemediationPrompt(
      {
        title: "a request has stopped making progress",
        text: "Request rq_1 stalled",
        agent: "bridge",
        ids: ["al_6aea"],
      },
      { generatedAt: "2026-11-28T13:54:42Z", host: "h" },
    );
    expect(out).toContain("# Follow-through needed:");
    expect(out).toContain("alert ids, not task ids");
    expect(out).not.toContain("Re-run the task");
  });
});
