type JsonRecord = Record<string, unknown>;

export type PostJson = (path: string, body: unknown) => Promise<unknown>;

export interface RedBoxFailure {
  expenseId: number | null;
  documentType: string;
  reason: string;
}

export interface RedBoxAudit {
  ok: boolean;
  checked: number;
  failures: RedBoxFailure[];
}

const EXPENSE_ID_KEYS = new Set([
  "expense_id",
  "expense_ids",
  "duplicate_expense_ids",
  "exact_duplicate_expense_id",
  "fuzzy_duplicate_expense_ids",
  "parent_expense_id",
  "child_expense_ids",
]);

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function positiveInteger(value: unknown): number | null {
  if (typeof value === "number" && Number.isInteger(value) && value > 0) {
    return value;
  }
  if (typeof value === "string" && /^[1-9]\d*$/.test(value)) {
    return Number(value);
  }
  return null;
}

function addExpenseIds(value: unknown, ids: Set<number>): void {
  const values = Array.isArray(value) ? value : [value];
  for (const candidate of values) {
    const parsed = positiveInteger(candidate);
    if (parsed !== null) ids.add(parsed);
  }
}

function collectIdsFromValue(
  value: unknown,
  ids: Set<number>,
  depth = 0,
): void {
  if (depth > 8) return;
  if (typeof value === "string") {
    const text = value.trim();
    if (!(text.startsWith("{") || text.startsWith("["))) return;
    try {
      collectIdsFromValue(JSON.parse(text), ids, depth + 1);
    } catch {
      return;
    }
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) collectIdsFromValue(item, ids, depth + 1);
    return;
  }
  if (!isRecord(value)) return;
  for (const [key, child] of Object.entries(value)) {
    if (EXPENSE_ID_KEYS.has(key)) addExpenseIds(child, ids);
    collectIdsFromValue(child, ids, depth + 1);
  }
}

function eventMatchesRun(
  event: JsonRecord,
  dispatchedAt: number,
  conversationId: string,
): boolean {
  if (event.conversation_id !== conversationId) return false;
  const eventDispatch =
    typeof event.dispatched_at === "number"
      ? event.dispatched_at
      : Number(event.dispatched_at);
  return (
    Number.isFinite(eventDispatch) &&
    Math.abs(eventDispatch - dispatchedAt) < 0.01
  );
}

export function collectExpenseIds(
  messagesValue: unknown,
  eventsValue: unknown,
  dispatchedAt: number,
  conversationId: string,
): number[] {
  const ids = new Set<number>();
  const messages = Array.isArray(messagesValue) ? messagesValue : [];
  const dispatchMs = dispatchedAt * 1000;
  for (const message of messages) {
    if (!isRecord(message)) continue;
    if (message.message_type !== "tool_return_message") continue;
    if (message.status === "error" || message.is_err === true) continue;
    const messageMs = Date.parse(
      typeof message.date === "string" ? message.date : "",
    );
    if (!Number.isFinite(messageMs) || messageMs < dispatchMs) continue;
    collectIdsFromValue(message.tool_return, ids);
    collectIdsFromValue(message.tool_returns, ids);
  }

  const eventList = Array.isArray(eventsValue)
    ? eventsValue
    : isRecord(eventsValue) && Array.isArray(eventsValue.events)
      ? eventsValue.events
      : [];
  for (const event of eventList) {
    if (
      !isRecord(event) ||
      !eventMatchesRun(event, dispatchedAt, conversationId)
    ) {
      continue;
    }
    collectIdsFromValue(event, ids);
  }
  return [...ids].sort((left, right) => left - right);
}

function availableViewerTypes(value: unknown): string[] {
  if (!isRecord(value) || !Array.isArray(value.documents)) return [];
  const types = new Set<string>();
  for (const document of value.documents) {
    if (!isRecord(document) || document.available !== true) continue;
    if (document.type === "receipt" || document.type === "source") {
      types.add(document.type);
    }
  }
  return [...types];
}

function responseReason(value: unknown, fallback: string): string {
  if (!isRecord(value)) return fallback;
  for (const key of ["highlight_note", "error", "reason"]) {
    const candidate = value[key];
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }
  return fallback;
}

export async function auditRedBoxesForRun(
  expenseIds: readonly number[],
  postJson: PostJson,
): Promise<RedBoxAudit> {
  if (expenseIds.length === 0) {
    return {
      ok: true,
      checked: 0,
      failures: [],
    };
  }

  const failures: RedBoxFailure[] = [];
  let checked = 0;
  for (const expenseId of expenseIds) {
    let descriptors: unknown;
    try {
      descriptors = await postJson("/api/supporting-documents", {
        expense_id: expenseId,
      });
    } catch (error) {
      failures.push({
        expenseId,
        documentType: "metadata",
        reason: `Supporting-document lookup failed: ${String(error)}`,
      });
      continue;
    }
    if (!isRecord(descriptors) || descriptors.ok !== true) {
      failures.push({
        expenseId,
        documentType: "metadata",
        reason: responseReason(
          descriptors,
          "Supporting-document lookup did not return ok=true.",
        ),
      });
      continue;
    }
    const viewerTypes = availableViewerTypes(descriptors);
    if (viewerTypes.length === 0) {
      failures.push({
        expenseId,
        documentType: "metadata",
        reason: "No receipt/source viewer is available for this expense.",
      });
      continue;
    }
    for (const documentType of viewerTypes) {
      checked += 1;
      let opened: unknown;
      try {
        opened = await postJson("/api/open-supporting-document", {
          expense_id: expenseId,
          document_type: documentType,
        });
      } catch (error) {
        failures.push({
          expenseId,
          documentType,
          reason: `Viewer request failed: ${String(error)}`,
        });
        continue;
      }
      if (
        !isRecord(opened) ||
        opened.ok !== true ||
        opened.highlighted !== true
      ) {
        failures.push({
          expenseId,
          documentType,
          reason: responseReason(
            opened,
            "Viewer did not return highlighted=true.",
          ),
        });
      }
    }
  }
  return { ok: failures.length === 0, checked, failures };
}

type TrainerVerdict = "PASS" | "CORRECTED" | "FAIL" | "STALLED" | "UNKNOWN";

function detectIntakeVerdict(report: string): TrainerVerdict {
  const priorGate = report.match(
    /Mazda intake (?:contract|verdict before this gate):\s*\*{0,2}(PASS|CORRECTED|FAIL|STALLED)\*{0,2}/i,
  );
  const verdict =
    priorGate ??
    report.match(/\bVerdict\b[^A-Za-z]*(PASS|CORRECTED|FAIL|STALLED)/i);
  return (
    (verdict?.[1]?.toUpperCase() as TrainerVerdict | undefined) ?? "UNKNOWN"
  );
}

function setOverallFailureVerdict(
  report: string,
  intakeVerdict: TrainerVerdict,
): string {
  const line =
    `**Verdict: FAIL (overall) — Mazda intake ${intakeVerdict}; ` +
    `dashboard red-box gate FAIL**`;
  const existingVerdictLine = /^.*\bVerdict\b.*$/im;
  if (existingVerdictLine.test(report)) {
    return report.replace(existingVerdictLine, line);
  }
  return `${line}\n\n${report}`;
}

function safeMarkdown(value: string): string {
  return value.replace(/\s+/g, " ").replaceAll("`", "'").trim();
}

export function applyRedBoxAuditToReport(
  reportValue: string,
  audit: RedBoxAudit,
): string {
  const intakeVerdict = detectIntakeVerdict(reportValue);
  const report = reportValue.replace(
    /\n## Deterministic red-box gate[\s\S]*$/i,
    "",
  );
  if (audit.ok) {
    return (
      `${report.trimEnd()}\n\n## Deterministic red-box gate — PASS\n\n` +
      `${audit.checked} available receipt/source viewer(s) returned ` +
      `\`highlighted=true\`.\n`
    );
  }

  const failures = audit.failures
    .map((failure) => {
      const expense =
        failure.expenseId === null
          ? "unknown expense"
          : `expense \`${failure.expenseId}\``;
      return (
        `- ${expense}, ${failure.documentType}: ` +
        `${safeMarkdown(failure.reason)}`
      );
    })
    .join("\n");
  return (
    `${setOverallFailureVerdict(report, intakeVerdict).trimEnd()}\n\n` +
    `## Deterministic red-box gate — FAIL\n\n` +
    `Mazda intake contract: **${intakeVerdict}**. ` +
    `Dashboard annotation verification: ` +
    `**FAIL**.\n\n${failures}\n\n` +
    `Do not coach Mazda, re-store the expense, or edit finance data for this ` +
    `failure. The red box is produced by ` +
    `\`dashboard/document_annotation.py\`; this is a dashboard defect.\n`
  );
}
