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

export interface RedBoxRunContext {
  docKind?: string;
  reason?: string;
  events?: unknown;
  dispatchedAt?: number;
  conversationId?: string;
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

function collectIdsFromLooseText(text: string, ids: Set<number>): void {
  const patterns = [
    /"expense_id"\s*:\s*(\d+)/g,
    /"expense_ids"\s*:\s*\[(.*?)\]/g,
    /"duplicate_expense_ids"\s*:\s*\[(.*?)\]/g,
  ];
  for (const pattern of patterns) {
    for (const match of text.matchAll(pattern)) {
      if (match[1] && /^\d+$/.test(match[1])) {
        ids.add(Number(match[1]));
        continue;
      }
      if (match[1]) {
        for (const num of match[1].matchAll(/\d+/g)) {
          ids.add(Number(num[0]));
        }
      }
    }
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
    if (text.startsWith("{") || text.startsWith("[")) {
      try {
        collectIdsFromValue(JSON.parse(text), ids, depth + 1);
        return;
      } catch {
        // Fall through to per-line parsing below — a Bash tool_return's
        // `stdout` field is captured CLI output, not a bare JSON document:
        // parse_and_categorize.py --save prints prose/log lines (including
        // Python dict reprs with single quotes, e.g. "Receipt metadata
        // create kwargs: {'expense_id': 1980, ...}") followed by exactly one
        // trailing JSON line. A whole-string parse failure here doesn't mean
        // no JSON is present.
      }
    }
    for (const line of text.split("\n")) {
      const trimmed = line.trim();
      if (!(trimmed.startsWith("{") || trimmed.startsWith("["))) continue;
      try {
        collectIdsFromValue(JSON.parse(trimmed), ids, depth + 1);
      } catch {
        // Not JSON (e.g. the single-quoted Python repr line above) — skip.
      }
    }
    // Regex fallback: catches expense-id patterns embedded in text that
    // never parses cleanly as JSON, whole or per-line (malformed fragments,
    // single-quoted Python reprs). Purely additive — never removes ids
    // already found above.
    collectIdsFromLooseText(text, ids);
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

function hasIntegrityError(
  eventsValue: unknown,
  dispatchedAt: number,
  conversationId: string,
): boolean {
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
    // Integrity error signature: parsed > 0, stored = 0, and both ID arrays empty
    const parsed = typeof event.parsed === "number" ? event.parsed : 0;
    const stored = typeof event.stored === "number" ? event.stored : 0;
    const expenseIds = Array.isArray(event.expense_ids)
      ? event.expense_ids
      : [];
    const duplicateIds = Array.isArray(event.duplicate_expense_ids)
      ? event.duplicate_expense_ids
      : [];

    if (
      parsed > 0 &&
      stored === 0 &&
      expenseIds.length === 0 &&
      duplicateIds.length === 0
    ) {
      return true;
    }
  }
  return false;
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
    const messageType = message.message_type;
    if (
      messageType !== "tool_return_message" &&
      messageType !== "tool_call_message"
    ) {
      continue;
    }
    if (
      messageType === "tool_return_message" &&
      (message.status === "error" || message.is_err === true)
    ) {
      continue;
    }
    const messageMs = Date.parse(
      typeof message.date === "string" ? message.date : "",
    );
    if (!Number.isFinite(messageMs) || messageMs < dispatchMs) continue;
    collectIdsFromValue(message.tool_return, ids);
    collectIdsFromValue(message.tool_returns, ids);
    collectIdsFromValue(message.tool_call, ids);
    collectIdsFromValue(message.tool_calls, ids);
    collectIdsFromValue(message.content, ids);
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
  runContext: RedBoxRunContext = {},
): Promise<RedBoxAudit> {
  if (expenseIds.length === 0) {
    const docKind =
      typeof runContext.docKind === "string"
        ? runContext.docKind.trim().toLowerCase()
        : "";
    const detail =
      typeof runContext.reason === "string" ? runContext.reason.trim() : "";

    // Check if this is a legitimate integrity-error case (statement/PDF duplicate
    // conflict where both expense_ids and duplicate_expense_ids were cleared)
    if (
      runContext.events !== undefined &&
      typeof runContext.dispatchedAt === "number" &&
      typeof runContext.conversationId === "string" &&
      hasIntegrityError(
        runContext.events,
        runContext.dispatchedAt,
        runContext.conversationId,
      )
    ) {
      // This is an expected outcome for a statement with duplicate callback mismatch -
      // not a dashboard annotation defect requiring follow-up
      return {
        ok: true,
        checked: 0,
        failures: [],
      };
    }

    const reason =
      docKind === "other"
        ? detail ||
          "Blank or non-financial scan produced no auditable expense IDs."
        : "No expense IDs were found for this intake run.";
    return {
      ok: false,
      checked: 0,
      failures: [
        {
          expenseId: null,
          documentType: "audit",
          reason,
        },
      ],
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
          // Browser clicks open immediately and prepare highlights in the
          // background. The Trainer explicitly waits because it grades the
          // annotation itself, not interactive viewer latency.
          wait_for_highlight: true,
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
