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

  test("collects expense IDs from tool_call_message arguments when event queue is empty", () => {
    const messages = [
      {
        date: "2026-07-30T16:25:06+00:00",
        message_type: "tool_call_message",
        tool_call: {
          name: "executor_run",
          arguments: JSON.stringify({
            command:
              "curl -s -X POST http://localhost:8765/api/expense-stored " +
              "-H 'Content-Type: application/json' " +
              '-d \'{"expense_id":1705,"expense_ids":[1705],' +
              '"duplicate_expense_ids":[],' +
              '"conversation_id":"conv-priority",' +
              '"dispatched_at":1785428583.2406921}\'',
          }),
        },
      },
      {
        date: "2026-07-30T16:25:13+00:00",
        message_type: "assistant_message",
        content: "Stored successfully as expense_id=1705",
      },
    ];

    expect(
      collectExpenseIds(messages, [], 1785428583.2406921, "conv-priority"),
    ).toEqual([1705]);
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

  test("fails closed when the run produced no auditable expense IDs", async () => {
    const audit = await auditRedBoxesForRun([], async () => {
      throw new Error("no API call should be made");
    });

    expect(audit.ok).toBe(false);
    expect(audit.checked).toBe(0);
    expect(audit.failures).toEqual([
      {
        expenseId: null,
        documentType: "audit",
        reason: "No expense IDs were found for this intake run.",
      },
    ]);
  });

  test("uses blank-scan wording for empty runs classified as other", async () => {
    const audit = await auditRedBoxesForRun(
      [],
      async () => {
        throw new Error("no API call should be made");
      },
      { docKind: "other" },
    );

    expect(audit.ok).toBe(false);
    expect(audit.checked).toBe(0);
    expect(audit.failures).toEqual([
      {
        expenseId: null,
        documentType: "audit",
        reason:
          "Blank or non-financial scan produced no auditable expense IDs.",
      },
    ]);
  });

  test("passes when empty expense IDs result from integrity error (duplicate callback mismatch)", async () => {
    const events = [
      {
        conversation_id: "conv-diners",
        dispatched_at: 1785500000.0,
        parsed: 2,
        stored: 0,
        expense_ids: [],
        duplicate_expense_ids: [],
      },
    ];

    const audit = await auditRedBoxesForRun(
      [],
      async () => {
        throw new Error("no API call should be made");
      },
      {
        docKind: "statement",
        events,
        dispatchedAt: 1785500000.0,
        conversationId: "conv-diners",
      },
    );

    expect(audit.ok).toBe(true);
    expect(audit.checked).toBe(0);
    expect(audit.failures).toEqual([]);
  });

  test("still fails for truly empty runs even with events present", async () => {
    const events = [
      {
        conversation_id: "conv-other",
        dispatched_at: 1785500000.0,
        parsed: 0,
        stored: 0,
        expense_ids: [],
        duplicate_expense_ids: [],
      },
    ];

    const audit = await auditRedBoxesForRun(
      [],
      async () => {
        throw new Error("no API call should be made");
      },
      {
        docKind: "statement",
        events,
        dispatchedAt: 1785500000.0,
        conversationId: "conv-other",
      },
    );

    expect(audit.ok).toBe(false);
    expect(audit.checked).toBe(0);
    expect(audit.failures).toEqual([
      {
        expenseId: null,
        documentType: "audit",
        reason: "No expense IDs were found for this intake run.",
      },
    ]);
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
