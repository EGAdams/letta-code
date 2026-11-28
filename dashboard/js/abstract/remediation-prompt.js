/**
 * Pure builder for the copy-paste remediation prompt behind the "Execute
 * agent" button on ReceptionistFailureAlert's cards. No DOM, no fetch: given
 * an alert's own metadata (the same shape receptionist-failure-alert.js
 * already holds per card) it derives a Claude-ready diagnostic prompt --
 * exact error, timestamp, host/agent/task IDs, related file paths it can
 * find in the text, a reproduction, expected vs actual, and acceptance
 * tests. Secrets are redacted before any of that text is assembled, so a
 * card that happens to echo a token or API key never puts it in a
 * clipboard-ready prompt.
 */

const SECRET_PATTERNS = [
  // Match bearer credentials before the generic labeled-pair rule so the
  // complete credential is consumed, rather than leaving its token behind.
  /\bBearer\s+[A-Za-z0-9._-]+/gi,
  // key/token/secret/password-shaped "name: value" or "name=value" pairs
  /\b[\w-]*(?:api[_-]?key|key|secret|token|password|passwd|authorization)[\w-]*\s*[:=]\s*["']?[^\s"'`,]+["']?/gi,
  /\bsk-[A-Za-z0-9_-]{10,}\b/g,
  /\bAKIA[0-9A-Z]{16}\b/g,
  /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g,
];

/** Replaces anything matching a known secret shape with "[REDACTED]". */
export function redactSecrets(text) {
  let out = String(text ?? "");
  for (const pattern of SECRET_PATTERNS)
    out = out.replace(pattern, "[REDACTED]");
  return out;
}

const PATH_PATTERN =
  /\b[\w.-]+(?:\/[\w.-]+)+\.(?:py|js|jsx|ts|tsx|json|html|css|sh|md|yml|yaml)(?::\d+)?\b/g;

/** De-duplicated file/code paths (optionally "file:line") found in `text`. */
export function extractPaths(text) {
  const matches = String(text ?? "").match(PATH_PATTERN) || [];
  const unique = [...new Set(matches)];
  return unique.filter(
    (path) =>
      /:\d+$/.test(path) ||
      !unique.some((other) => other.startsWith(`${path}:`)),
  );
}

/**
 * @param {object} alert - {title, text, agent, severity, outcome, ids, sources, key}
 * @param {object} [opts] - {generatedAt, host} injected for deterministic output in tests
 */
export function buildRemediationPrompt(alert, { generatedAt, host } = {}) {
  const title = redactSecrets(alert?.title || "an alert");
  const text = redactSecrets(alert?.text || "");
  const agent = alert?.agent || "unknown agent";
  const severity = alert?.severity || "notice";
  const outcome = alert?.outcome || "unknown";
  const ids = (alert?.ids || []).filter(Boolean);
  const when = generatedAt || new Date().toISOString();
  const where =
    host ||
    (typeof globalThis !== "undefined" ? globalThis.location?.hostname : "") ||
    "unknown host";
  // A Star Trek Bridge gateway alert (al_...) reports the state of a request or
  // task. There is no failed run to repeat, so it gets follow-through steps.
  const fromGateway = ids.length > 0 && ids.every((id) => /^al_/.test(id));
  const paths = extractPaths(text);
  const related = (alert?.sources || [])
    .filter(
      (s) => s && (s.title || s.text) && redactSecrets(s.text || "") !== text,
    )
    .map((s) =>
      `- ${redactSecrets(s.title || "")}: ${redactSecrets(s.text || "")}`.trim(),
    );

  const secrets = [
    "",
    "## Secrets",
    "Any credentials, tokens, or keys detected above have been redacted; do not reintroduce real secrets into code, logs, or commit messages.",
  ];
  if (fromGateway) {
    return [
      `# Follow-through needed: ${title}`,
      "",
      "## What the Bridge reports",
      text || "(no alert text was reported)",
      "",
      "## Context",
      `- Timestamp: ${when}`,
      `- Host: ${where}`,
      `- Severity: ${severity}`,
      `- Alert ID(s): ${ids.join(", ")} (alert ids, not task ids)`,
      "",
      "## What to do",
      "1. Read the current record first (request_status or get_agent_task_result); it may have moved on.",
      "2. Do the next step once, or record the real blocker and its owner, or close it with the reason.",
      "3. Never resend a task, print or mail to clear an alert, and never add a progress note only to reset the timer.",
      "4. Change code only if the record itself is wrong, and then say which part.",
      "",
      "## Done when",
      "- [ ] The request has evidence of completion, a named blocker and owner, or a recorded reason for closing it.",
      ...secrets,
    ].join("\n");
  }

  const lines = [
    `# Remediation request: ${title}`,
    "",
    "## Exact error",
    text || "(no error text was reported)",
    "",
    "## Context",
    `- Timestamp: ${when}`,
    `- Host: ${where}`,
    `- Agent: ${agent}`,
    `- Task ID(s): ${ids.length ? ids.join(", ") : "none reported"}`,
    `- Severity: ${severity}`,
    `- Outcome: ${outcome}`,
    "",
    "## Related files/paths",
    paths.length
      ? paths.map((p) => `- ${p}`).join("\n")
      : "- None detected in the alert text.",
  ];
  if (related.length) {
    lines.push("", "## Related signals", ...related);
  }
  lines.push(
    "",
    "## Reproduction",
    `1. Re-run the task/alert path for ${agent}${ids.length ? ` (task ${ids.join(", ")})` : ""} that produced the error above.`,
    "2. Confirm the same error text recurs before changing anything.",
    "",
    "## Expected vs actual",
    "- Expected: the task completes without the error above.",
    `- Actual: ${text || "(no error text was reported)"}`,
    "",
    "## Acceptance tests",
    "- [ ] The exact error text above no longer occurs for this agent/task.",
    "- [ ] A new or updated automated test reproduces the original failure and asserts it is fixed.",
    "- [ ] The existing test suite still passes.",
    ...secrets,
  );
  return lines.join("\n");
}
