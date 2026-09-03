/** Pure agreements for the three manual receipt-reading commands. */
import { readPrefillResponse } from "./manual-entry.interface.js";
import { readStatementBreakupResponse } from "./statement-breakup.interface.js";

export const RECEIPT_READ_INTENT = Object.freeze({
  CIRCLED_ONLY: "circled-only",
  TOTAL_ONLY: "total-only",
  SEVERAL_EXPENSES: "several-expenses",
});

export const RECEIPT_READ_ACTIONS = Object.freeze([
  {
    intent: RECEIPT_READ_INTENT.CIRCLED_ONLY,
    label: "Circled Only",
    progressSeconds: 15,
  },
  {
    intent: RECEIPT_READ_INTENT.TOTAL_ONLY,
    label: "Total Only",
    progressSeconds: 8,
  },
  {
    intent: RECEIPT_READ_INTENT.SEVERAL_EXPENSES,
    label: "Several Expenses",
    progressSeconds: 17,
  },
]);

export const RECEIPT_READ_MODELS = Object.freeze([
  { model: "gemini-only", label: "Gemini Flash" },
  { model: "haiku-only", label: "Claude Haiku" },
  { model: "codex-only", label: "Codex (luna)" },
]);

export const DEFAULT_RECEIPT_READ_MODEL = "gemini-only";

export const FILL_SHAPE = Object.freeze({
  ONE_EXPENSE: "one-expense",
  MANY_EXPENSES: "many-expenses",
});

export function receiptReadModelLabel(model) {
  const found = RECEIPT_READ_MODELS.find((option) => option.model === model);
  return found ? found.label : model || "";
}

export function receiptReadAction(intent) {
  return (
    RECEIPT_READ_ACTIONS.find((action) => action.intent === intent) ||
    RECEIPT_READ_ACTIONS[1]
  );
}

export function buildReceiptReadPayload(
  intakeRef,
  intent,
  model,
  statementMetadata,
) {
  return {
    image_path: intakeRef.imagePath,
    intent,
    model,
    bank_name: ((statementMetadata && statementMetadata.bankName) || "").trim(),
    account_last4: (
      (statementMetadata && statementMetadata.accountLast4) ||
      ""
    ).trim(),
  };
}

export function readReceiptReadResponse(json) {
  const object = typeof json === "object" && json !== null ? json : {};
  const shape =
    object.shape === FILL_SHAPE.MANY_EXPENSES
      ? FILL_SHAPE.MANY_EXPENSES
      : FILL_SHAPE.ONE_EXPENSE;
  const statement = readStatementBreakupResponse(object.statement);
  return {
    ok: object.ok === true,
    shape,
    intent:
      typeof object.intent === "string"
        ? object.intent
        : RECEIPT_READ_INTENT.TOTAL_ONLY,
    model: typeof object.model === "string" ? object.model : "",
    docKind: typeof object.doc_kind === "string" ? object.doc_kind : "",
    prefill: readPrefillResponse(object.receipt),
    items: statement.items,
    excludedRows: statement.excludedRows,
    header: statement.header,
    needsStatementMetadata: statement.needsStatementMetadata,
    missingFields: statement.missingFields,
    error: typeof object.error === "string" ? object.error : null,
    rereadAfter:
      typeof object.reread_after === "string" ? object.reread_after : "",
  };
}

export function summarizeReceiptReread(result) {
  if (!result || !result.rereadAfter) return "";
  return ` Read as a receipt first, then re-read as a statement: ${result.rereadAfter}`;
}
