import { describe, expect, test } from "bun:test";

import {
  applyRedBoxAuditToReport,
  auditRedBoxesForRun,
  collectExpenseIds,
} from "./red-box-gate.ts";

describe("Trainer deterministic red-box gate", () => {
  test("collects parent and child expense IDs from successful transcript returns", () => {
    const messages = [
      {
        date: "2026-07-29T13:04:00+00:00",
        message_type: "tool_return_message",
        status: "success",
        tool_return: JSON.stringify({
          ok: true,
          parent_expense_id: 1678,
          child_expense_ids: [1679, 1680, 1681, 1682, 1683],
        }),
      },
      {
        date: "2026-07-29T12:59:00+00:00",
        message_type: "tool_return_message",
        status: "success",
        tool_return: JSON.stringify({ expense_id: 1 }),
      },
      {
        date: "2026-07-29T13:04:01+00:00",
        message_type: "tool_return_message",
        status: "error",
        tool_return: JSON.stringify({ expense_id: 2 }),
      },
    ];
    const events = [
      {
        conversation_id: "conv-freezer",
        dispatched_at: 1785330070.6089723,
        expense_ids: [1678],
        duplicate_expense_ids: [1600],
      },
      {
        conversation_id: "conv-other",
        dispatched_at: 1785330070.6089723,
        expense_ids: [9999],
      },
    ];

    expect(
      collectExpenseIds(messages, events, 1785330070.6089723, "conv-freezer"),
    ).toEqual([1600, 1678, 1679, 1680, 1681, 1682, 1683]);
  });

  test("finds an expense id in a Bash tool_return's captured stdout, not just bare JSON", () => {
    // Real shape from the 2026-08-02 Dermatology Associates freezer scan
    // (expense 1980): parse_and_categorize.py --save prints a Python dict
    // repr line ("Receipt metadata create kwargs: {'expense_id': 1980, ...}",
    // single-quoted — not JSON) followed by log/warning lines, then exactly
    // one trailing JSON line with the real result. Before this fix,
    // collectIdsFromValue only parsed a tool_return string when the *entire*
    // trimmed string was JSON, so this run's stdout was skipped outright and
    // the deterministic gate reported "PASS — 0 checked" instead of catching
    // that the receipt was never red-boxed.
    const stdout =
      "Receipt metadata create kwargs: {'expense_id': 1980, 'model_name': 'gemini'}\n" +
      "Receipt metadata row: {'id': 132, 'expense_id': 1980}\n" +
      `${JSON.stringify({ success: true, expense_id: 1980, duplicate: false })}\n`;
    const messages = [
      {
        date: "2026-08-02T01:54:23+00:00",
        message_type: "tool_return_message",
        status: "success",
        tool_return: JSON.stringify({
          returncode: 0,
          stdout,
          stderr: "WARNING:__main__:Source-counterpart lookup failed\n",
          cwd_resolved: "/home/adamsl/rol_finances",
        }),
      },
    ];

    expect(collectExpenseIds(messages, [], 1785635468, "conv-freezer")).toEqual(
      [1980],
    );
  });

  test("audits every available viewer and reports an unboxed child", async () => {
    const calls: Array<[string, unknown]> = [];
    const postJson = async (path: string, body: unknown): Promise<unknown> => {
      calls.push([path, body]);
      const request = body as { expense_id: number; document_type?: string };
      if (path === "/api/supporting-documents") {
        return {
          ok: true,
          documents: [
            { type: "receipt", available: true },
            { type: "source", available: false },
          ],
        };
      }
      return {
        ok: true,
        highlighted: request.expense_id !== 1680,
        highlight_note:
          request.expense_id === 1680
            ? "No high-confidence expense row was found in the image."
            : "",
      };
    };

    const audit = await auditRedBoxesForRun([1679, 1680], postJson);

    expect(audit.ok).toBe(false);
    expect(audit.checked).toBe(2);
    expect(audit.failures).toEqual([
      {
        expenseId: 1680,
        documentType: "receipt",
        reason: "No high-confidence expense row was found in the image.",
      },
    ]);
    expect(calls).toHaveLength(4);
  });

  test("treats runs with no auditable expense IDs as a dashboard no-op", async () => {
    const audit = await auditRedBoxesForRun([], async () => {
      throw new Error("no API call should be made");
    });

    expect(audit.ok).toBe(true);
    expect(audit.checked).toBe(0);
    expect(audit.failures).toEqual([]);
  });

  test("fails closed when an expense has no available receipt or source viewer", async () => {
    const audit = await auditRedBoxesForRun([1680], async () => ({
      ok: true,
      documents: [
        { type: "receipt", available: false },
        { type: "source", available: false },
      ],
    }));

    expect(audit.ok).toBe(false);
    expect(audit.checked).toBe(0);
    expect(audit.failures).toEqual([
      {
        expenseId: 1680,
        documentType: "metadata",
        reason: "No receipt/source viewer is available for this expense.",
      },
    ]);
  });

  test("rewrites a false Trainer PASS without blaming Mazda", () => {
    const report =
      "# Trainer Report\n\n- Verdict: PASS\n\nMazda completed intake.\n";
    const updated = applyRedBoxAuditToReport(report, {
      ok: false,
      checked: 6,
      failures: [
        {
          expenseId: 1680,
          documentType: "receipt",
          reason: "No high-confidence expense row was found in the image.",
        },
      ],
    });

    expect(updated).toContain(
      "**Verdict: FAIL (overall) — Mazda intake PASS; " +
        "dashboard red-box gate FAIL**",
    );
    expect(updated).not.toContain("FAIL (intake)");
    expect(updated).toContain("Mazda intake contract: **PASS**");
    expect(updated).toContain("Dashboard annotation verification: **FAIL**");
    expect(updated).toContain("expense `1680`");
    expect(updated).toContain("Do not coach Mazda");
  });

  test("normalizes a composite verdict without changing intake PASS to intake FAIL", () => {
    const report =
      "**Verdict: PASS (intake) / FAIL (red-box gate — dashboard defect)**\n";
    const updated = applyRedBoxAuditToReport(report, {
      ok: false,
      checked: 1,
      failures: [
        {
          expenseId: 1680,
          documentType: "receipt",
          reason: "No high-confidence expense row was found in the image.",
        },
      ],
    });

    expect(updated).toContain("Mazda intake PASS");
    expect(updated).not.toContain("FAIL (intake)");
  });
});
