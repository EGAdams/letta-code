// scan_01M6D5T6XEKGP8V3WTSYY2QPB7 regression (2026-11-01): a city-tax
// instruction sheet Mazda classified, archived and extracted was failed by
// the red-box gate for having no expense IDs, and its status reached the
// dashboard with an empty detail. Neutral fixtures, no production data.
import { describe, expect, test } from "bun:test";
import { intakeStatusDetail } from "./intake-status-detail.ts";
import {
  applyRedBoxAuditToReport,
  auditRedBoxesForRun,
  type RedBoxAudit,
} from "./red-box-gate.ts";

const CONV = "conv-test-1";
const AT = 1762000000.25;
const ARCHIVE = "/archive/tax_documents/city_tax_instructions/page.jpg";

function callback(overrides: Record<string, unknown> = {}) {
  return {
    kind: "document",
    conversation_id: CONV,
    dispatched_at: AT,
    doc_kind: "tax_document",
    parsed: 0,
    stored: 0,
    expense_ids: [],
    duplicate_expense_ids: [],
    archive_paths: [ARCHIVE],
    ...overrides,
  };
}

const neverCalled = async () => {
  throw new Error("no viewer lookup expected for a zero-ID run");
};

async function gate(events: unknown[], docKind = "unknown") {
  return auditRedBoxesForRun([], neverCalled, {
    docKind,
    events,
    dispatchedAt: AT,
    conversationId: CONV,
  });
}

const TRAINER_REPORT =
  "# Mazda intake report\n\n**Verdict: PASS**\n\nArchived and extracted.\n";

describe("expense audit applicability", () => {
  test("1. valid tax instructions: not applicable, report keeps success", async () => {
    const audit = await gate([callback()]);
    expect(audit.ok).toBe(true);
    expect(audit.applicable).toBe(false);
    expect(audit.reason).toContain("tax_document");
    const report = applyRedBoxAuditToReport(TRAINER_REPORT, audit);
    expect(report).toContain("## Deterministic red-box gate — NOT APPLICABLE");
    expect(report).toContain("**Verdict: PASS**");
    expect(report).not.toContain("FAIL (overall)");
  });

  test("2. preliminary unknown, final tax_document: same result", async () => {
    const audit = await gate([callback()], "unknown");
    expect(audit.applicable).toBe(false);
    expect(audit.ok).toBe(true);
  });

  test("3. valid other document: not applicable", async () => {
    const audit = await gate([callback({ doc_kind: "other" })], "other");
    expect(audit.applicable).toBe(false);
    expect(audit.reason).toContain("other");
  });

  test("4a. final classification unknown: no automatic pass", async () => {
    const audit = await gate([callback({ doc_kind: "unknown" })]);
    expect(audit.ok).toBe(false);
    expect(audit.failures[0].reason).toContain("unknown");
  });

  test("4b. no completion callback: no automatic pass", async () => {
    const audit = await gate([], "tax_document");
    expect(audit.ok).toBe(false);
    expect(audit.applicable).not.toBe(false);
    expect(audit.failures[0].reason).not.toBe("");
  });

  test("4c. another intake's callback is never attached", async () => {
    const otherRun = await gate([callback({ conversation_id: "conv-other" })]);
    expect(otherRun.ok).toBe(false);
    const sameConvOtherDispatch = await gate([
      callback({ dispatched_at: AT + 5 }),
    ]);
    expect(sameConvOtherDispatch.ok).toBe(false);
  });

  test("4d. malformed callback is not a pass", async () => {
    const audit = await gate([
      { conversation_id: CONV, dispatched_at: "x" },
      "junk",
    ]);
    expect(audit.ok).toBe(false);
  });

  test("5. tax document with no archive: fails with an explanation", async () => {
    const audit = await gate([callback({ archive_paths: [] })]);
    expect(audit.ok).toBe(false);
    expect(audit.failures[0].reason).toContain("no archive path");
    const report = applyRedBoxAuditToReport(TRAINER_REPORT, audit);
    expect(report).toContain("dashboard red-box gate FAIL");
  });

  test("6. receipt with zero expense IDs still fails", async () => {
    const audit = await gate([callback({ doc_kind: "receipt" })], "receipt");
    expect(audit.ok).toBe(false);
    expect(audit.failures[0].reason).toBe(
      "No expense IDs were found for this intake run.",
    );
  });

  test("7. duplicate-only statement keeps its integrity exception", async () => {
    const audit = await gate(
      [
        callback({
          doc_kind: "statement",
          parsed: 3,
          stored: 0,
          archive_paths: [],
        }),
      ],
      "statement",
    );
    expect(audit.ok).toBe(true);
    expect(audit.applicable).toBeUndefined();
  });

  test("8. any document with expense IDs runs the red-box checks", async () => {
    const posted: string[] = [];
    const audit = await auditRedBoxesForRun(
      [42],
      async (path) => {
        posted.push(path);
        return { ok: false, error: "fixture" };
      },
      {
        docKind: "tax_document",
        events: [callback()],
        dispatchedAt: AT,
        conversationId: CONV,
      },
    );
    expect(posted).toContain("/api/supporting-documents");
    expect(audit.ok).toBe(false);
    expect(audit.applicable).toBeUndefined();
  });

  test("N/A replay restores only the gate's own composite verdict line", () => {
    const rewritten =
      "**Verdict: FAIL (overall) — Mazda intake PASS; dashboard red-box gate FAIL**\n\n" +
      "body\n\n## Deterministic red-box gate — FAIL\n\nold\n";
    const audit: RedBoxAudit = {
      ok: true,
      checked: 0,
      failures: [],
      applicable: false,
      reason: "n/a reason",
    };
    const report = applyRedBoxAuditToReport(rewritten, audit);
    expect(report).not.toContain("FAIL (overall)");
    expect(report).toContain("Verdict: PASS");
    expect(report).not.toContain("old");
    // A failure the Trainer itself reported survives N/A untouched.
    const trainerFail = applyRedBoxAuditToReport(
      "**Verdict: FAIL**\n\nx\n",
      audit,
    );
    expect(trainerFail).toContain("**Verdict: FAIL**");
  });
});

describe("intake status detail", () => {
  test("9. no Diagnosis, but gate and Escalation: the detail survives", () => {
    const report =
      "**Verdict: FAIL (overall) — Mazda intake FAIL; dashboard red-box gate FAIL**\n\n" +
      "## Escalation\n\nCallback reported no parsed or persisted records.\n\n" +
      "## Deterministic red-box gate — FAIL\n\n- unknown expense, audit: No expense IDs.\n";
    const detail = intakeStatusDetail(
      report,
      "fail",
      {
        ok: false,
        failures: [
          { reason: "No expense IDs were found for this intake run." },
        ],
      },
      "r.md",
    );
    expect(detail).toContain("No expense IDs were found");
    expect(detail).toContain("Escalation: Callback reported no parsed");
    expect(detail.length).toBeLessThanOrEqual(1000);
  });

  test("9b. falls back to the report's gate section without a structured result", () => {
    const report =
      "**Verdict: FAIL**\n\n## Deterministic red-box gate — FAIL\n\n- bad box\n";
    expect(intakeStatusDetail(report, "fail", undefined, "r.md")).toContain(
      "bad box",
    );
  });

  test("9c. Diagnosis and Wrapper Defect still read", () => {
    expect(
      intakeStatusDetail(
        "## Diagnosis\n\nwrong vendor\n",
        "fail",
        undefined,
        "r.md",
      ),
    ).toContain("wrong vendor");
    expect(
      intakeStatusDetail(
        "## Wrapper Defect\n\ntool crashed\n",
        "stalled",
        undefined,
        "r.md",
      ),
    ).toContain("tool crashed");
  });

  test("10. nothing to explain: an honest non-empty message", () => {
    const detail = intakeStatusDetail(
      "**Verdict: FAIL**\n",
      "fail",
      undefined,
      "r.md",
    );
    expect(detail).toBe(
      "Trainer reported fail but no upstream diagnostic was recorded; see report r.md.",
    );
    expect(
      intakeStatusDetail("**Verdict: PASS**\n", "pass", undefined, "r.md"),
    ).toBe("");
  });
});
