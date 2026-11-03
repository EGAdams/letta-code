// Whether the red-box expense audit applies to an intake that produced no
// expense IDs. Only Mazda's own completion callback for THIS dispatch
// (exact conversation_id + dispatched_at) can say "nothing to audit"; the
// facade's preliminary doc_kind, a scanner name, or a timestamp alone never
// can. Only the expense audit is exempted -- the document must still have
// been classified, completed and archived, or the gate fails with a reason.

type JsonRecord = Record<string, unknown>;

/** Final kinds Mazda files rather than stores as expenses. */
export const NON_EXPENSE_DOC_KINDS: ReadonlySet<string> = new Set([
  "tax_document",
  "other",
]);

export interface ExpenseAuditApplicability {
  /** false = the expense audit does not apply (an explicit pass of that check only). */
  applicable: boolean;
  /** Why; always non-empty when Mazda's final callback said something we could use. */
  reason: string;
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function eventList(eventsValue: unknown): unknown[] {
  if (Array.isArray(eventsValue)) return eventsValue;
  if (isRecord(eventsValue) && Array.isArray(eventsValue.events)) {
    return eventsValue.events;
  }
  return [];
}

/** The one identity rule: exact conversation and dispatch time. */
export function eventMatchesRun(
  event: JsonRecord,
  dispatchedAt: number,
  conversationId: string,
): boolean {
  if (!conversationId || event.conversation_id !== conversationId) return false;
  const eventDispatch =
    typeof event.dispatched_at === "number"
      ? event.dispatched_at
      : Number(event.dispatched_at);
  return (
    Number.isFinite(eventDispatch) &&
    Math.abs(eventDispatch - dispatchedAt) < 0.01
  );
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function nonEmptyStrings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item) => typeof item === "string" && item.trim() !== "")
    : [];
}

/**
 * Decide applicability for a zero-expense-ID run. Returns null when no
 * callback for this exact intake exists, or when Mazda's final kind is an
 * expense kind -- the caller then keeps its ordinary "no expense IDs" failure.
 */
export function expenseAuditApplicability(
  eventsValue: unknown,
  dispatchedAt: number | undefined,
  conversationId: string | undefined,
): ExpenseAuditApplicability | null {
  if (typeof dispatchedAt !== "number" || typeof conversationId !== "string") {
    return null;
  }
  const matched = eventList(eventsValue).filter(
    (event): event is JsonRecord =>
      isRecord(event) && eventMatchesRun(event, dispatchedAt, conversationId),
  );
  if (matched.length === 0) return null;

  const finalKind = String(matched[matched.length - 1]?.doc_kind ?? "")
    .trim()
    .toLowerCase();
  if (finalKind === "unknown") {
    return {
      applicable: true,
      reason:
        "No expense IDs were found for this intake run, and Mazda's final " +
        "classification was unknown; nothing can be exempted.",
    };
  }
  if (!NON_EXPENSE_DOC_KINDS.has(finalKind)) return null;

  const stored = matched.some(
    (event) =>
      count(event.stored) > 0 ||
      count(event.parsed) > 0 ||
      event.expense_id != null ||
      nonEmptyStrings(event.expense_ids).length > 0 ||
      (Array.isArray(event.expense_ids) && event.expense_ids.length > 0),
  );
  if (stored) {
    return {
      applicable: true,
      reason:
        `Mazda classified this intake as ${finalKind} but her callback ` +
        "reported parsed or stored records with no expense IDs to audit.",
    };
  }
  const archived = matched.some(
    (event) => nonEmptyStrings(event.archive_paths).length > 0,
  );
  if (!archived) {
    return {
      applicable: true,
      reason:
        `Mazda classified this intake as ${finalKind} but her callback ` +
        "reported no archive path, so filing is not evidenced.",
    };
  }
  return {
    applicable: false,
    reason:
      `Expense audit not applicable: Mazda's final classification for this ` +
      `intake is ${finalKind}, it was archived, and no expenses were expected.`,
  };
}

/**
 * Report section for a not-applicable gate. The verdict line is the
 * Trainer's own; only a composite line this gate itself wrote on an earlier
 * pass is restored to the intake verdict, so N/A neither manufactures nor
 * erases a failure.
 */
export function renderNotApplicableGate(
  report: string,
  intakeVerdict: string,
  reason: string,
): string {
  const ownComposite =
    /^\*\*Verdict: FAIL \(overall\) — Mazda intake (PASS|CORRECTED|FAIL|STALLED); dashboard red-box gate FAIL\*\*$/im;
  const restored = report.replace(
    ownComposite,
    (_line, verdict: string) =>
      `**Verdict: ${verdict} — dashboard red-box gate NOT APPLICABLE**`,
  );
  return (
    `${restored.trimEnd()}\n\n## Deterministic red-box gate — NOT APPLICABLE\n\n` +
    `${reason.replace(/\s+/g, " ").trim()}\n\n` +
    `Mazda intake contract: **${intakeVerdict}**. Only the expense red-box ` +
    `audit is exempted; classification, completion and archiving were ` +
    `checked above.\n`
  );
}
