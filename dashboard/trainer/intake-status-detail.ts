// The one-line explanation the Trainer posts with an intake status. A
// non-pass status must never arrive with an empty detail: the structured
// gate result is preferred, report sections are the fallback, and when
// neither says anything the detail says that honestly.

export const STATUS_DETAIL_LIMIT = 1000;

/** Report sections that explain a verdict, most specific first. */
const EXPLAINING_SECTIONS = [
  "Diagnosis",
  "Wrapper Defect",
  "Escalation",
  "Grader Defect",
  "Deterministic red-box gate",
];

export interface GateOutcome {
  ok: boolean;
  applicable?: boolean;
  reason?: string;
  failures?: ReadonlyArray<{ reason: string }>;
}

function squash(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Body of a `## <name>` section; the heading may carry a suffix ("— FAIL"). */
export function reportSection(report: string, name: string): string {
  const heading = new RegExp(
    `^## ${escapeRegExp(name)}\\b[^\\n]*\\n([\\s\\S]*?)(?=\\n## |(?![\\s\\S]))`,
    "im",
  );
  return squash(report.match(heading)?.[1] ?? "");
}

function gateDetail(gate: GateOutcome | undefined): string {
  if (!gate) return "";
  if (gate.applicable === false) return squash(gate.reason ?? "");
  if (gate.ok) return "";
  const reasons = (gate.failures ?? [])
    .map((failure) => squash(failure.reason ?? ""))
    .filter(Boolean);
  return reasons.length
    ? `Dashboard red-box gate FAIL: ${reasons.join("; ")}`
    : "";
}

export function intakeStatusDetail(
  report: string,
  status: string,
  gate: GateOutcome | undefined,
  reportName: string,
): string {
  const parts: string[] = [];
  const fromGate = gateDetail(gate);
  for (const name of EXPLAINING_SECTIONS) {
    if (name === "Deterministic red-box gate" && fromGate) continue;
    const body = reportSection(report, name);
    if (body) parts.push(`${name}: ${body}`);
  }
  if (fromGate) parts.unshift(fromGate);
  let detail = parts.join(" | ");
  if (!detail && status.toLowerCase() !== "pass") {
    detail =
      `Trainer reported ${status.toLowerCase()} but no upstream diagnostic ` +
      `was recorded; see report ${reportName}.`;
  }
  return detail.slice(0, STATUS_DETAIL_LIMIT);
}
