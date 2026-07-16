#!/usr/bin/env bun
// Mazda Trainer — dynamically builds a Claude agent (via claude-code-sdk-ts) that
// watches ONE Mazda intake run, verifies it, and coaches Mazda on failures.
// If a Claude session fails outright (quota/auth/crash/timeout), the watchdog
// falls back to `codex exec` (gpt-5.4-mini) for the remaining attempts.
//
// Fired fire-and-forget by dashboard/server.py (_notify_trainer_of_scan) every time
// a scan is dispatched to Mazda. Can also be run by hand:
//
//   bun run_mazda_trainer.mjs --scan-path /path/on/executor/scan.jpg \
//       --scanner "Window Scanner" --facade '{"ok":true,...}' \
//       --dispatched-at 1752170000 --conversation-id conv-...
//
// The agent's system message = mazda_trainer_instructions.md + the text of
// notes_plans_handoffs/mazda_dev_status.html (Mazda's developer manual).

import { mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { claude } from '/home/adamsl/claude-code-sdk-ts/dist/index.js';

const HERE = dirname(fileURLToPath(import.meta.url));

// The SDK spawns the `claude` CLI with our env. An inherited ANTHROPIC_API_KEY
// silently outranks the OAuth login and can point at a creditless API account
// ("Credit balance is too low" → CLI exit 1 mid-run). CLAUDECODE /
// CLAUDE_CODE_ENTRYPOINT leak when launched from inside a Claude Code session
// and confuse the nested CLI. Strip all three so the trainer always runs on
// this box's OAuth login regardless of who launched it.
delete process.env.ANTHROPIC_API_KEY;
delete process.env.CLAUDECODE;
delete process.env.CLAUDE_CODE_ENTRYPOINT;

const INSTRUCTIONS_PATH = join(HERE, 'mazda_trainer_instructions.md');
const MANUAL_PATH = join(HERE, '..', '..', 'notes_plans_handoffs', 'mazda_dev_status.html');

const LETTA_BASE_URL = process.env.LETTA_BASE_URL || 'http://100.80.49.10:8283';
const DASHBOARD_BASE_URL = process.env.DASHBOARD_BASE_URL || 'http://localhost:8765';
const MAZDA_AGENT_ID =
  process.env.MAZDA_AGENT_ID || 'agent-6b536cf4-ec88-4290-b595-fed21d14bd8e';
const TRAINER_MODEL = process.env.TRAINER_MODEL || 'sonnet';
// Fallback when the Claude session itself fails; gpt-5.4-mini is the vetted
// ChatGPT-OAuth mini handle (plain gpt-5-mini is rejected by the provider).
const TRAINER_CODEX_MODEL = process.env.TRAINER_CODEX_MODEL || 'gpt-5.4-mini';
const CODEX_BIN = process.env.MAZDA_TRAINER_CODEX_BIN || 'codex';
const TRAINER_TIMEOUT_MS = Number(process.env.TRAINER_TIMEOUT_MS || 35 * 60 * 1000);
// Cap any single session below the overall budget so a session that dies at the
// buzzer (e.g. timing out mid-Write, seen 2026-07-13) still leaves the watchdog
// room to relaunch and salvage the report.
const TRAINER_ATTEMPT_TIMEOUT_MS =
  Number(process.env.TRAINER_ATTEMPT_TIMEOUT_MS || 20 * 60 * 1000);

function parseArgs(argv) {
  const args = { facade: '{}' };
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (key === '--scan-path') args.scanPath = argv[++i];
    else if (key === '--scanner') args.scanner = argv[++i];
    else if (key === '--facade') args.facade = argv[++i];
    else if (key === '--dispatched-at') args.dispatchedAt = argv[++i];
    else if (key === '--conversation-id') args.conversationId = argv[++i];
    else if (key === '--dry-run') args.dryRun = true;
  }
  if (!args.scanPath || !args.scanner) {
    console.error('Usage: run_mazda_trainer.mjs --scan-path <path> --scanner <name> ' +
      '[--facade <json>] [--dispatched-at <unix ts>] [--conversation-id <id>]');
    process.exit(2);
  }
  if (!args.dispatchedAt) args.dispatchedAt = String(Math.floor(Date.now() / 1000));
  if (!args.conversationId && !args.dryRun) {
    console.error('--conversation-id is required so concurrent intakes cannot share context');
    process.exit(2);
  }
  return args;
}

function buildReportPath(args) {
  const stamp = new Date(Number(args.dispatchedAt) * 1000)
    .toISOString().replace(/[-:]/g, '').replace('T', '-').slice(0, 15);
  const scanner = args.scanner.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_|_$/g, '');
  const dispatch = String(args.dispatchedAt).replace(/[^0-9]/g, '');
  return join(HERE, 'reports', `${stamp}_${scanner || 'scanner'}_d${dispatch}.md`);
}

// The manual is HTML meant for a browser; strip it to readable text so it fits the
// system message without wasting tokens on markup.
function htmlToText(html) {
  return html
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function buildSystemMessage() {
  const instructions = readFileSync(INSTRUCTIONS_PATH, 'utf8');
  const manual = htmlToText(readFileSync(MANUAL_PATH, 'utf8'));
  return `${instructions}\n\n---\n\n# APPENDIX — Mazda: A Developer's Manual\n\n${manual}`;
}

function buildTaskMessage(args) {
  const dispatchedIso = new Date(Number(args.dispatchedAt) * 1000).toISOString();
  return [
    'A document was just scanned and dispatched to Mazda. Watch this run per your',
    'instructions, verify it, coach her if needed, and write your report.',
    '',
    `Scanner: ${args.scanner}`,
    `Scanned image (path as Mazda's executor sees it): ${args.scanPath}`,
    `Dispatch timestamp: ${args.dispatchedAt} (${dispatchedIso}) — ignore transcript entries older than this.`,
    `Mazda conversation ID: ${args.conversationId || '(dry-run placeholder)'}`,
    `Required report path for THIS run: ${args.reportPath}`,
    `Deterministic facade result: ${args.facade}`,
    '',
    'Environment values for your curl commands:',
    `  LETTA_BASE_URL=${LETTA_BASE_URL}`,
    `  MAZDA_AGENT_ID=${MAZDA_AGENT_ID}`,
    `  MAZDA_CONVERSATION_ID=${args.conversationId || ''}`,
    `  MAZDA_TRAINER_REPORT_PATH=${args.reportPath}`,
  ].join('\n');
}

async function runClaudeAttempt(prompt, timeoutMs, args) {
  return claude()
    .withModel(TRAINER_MODEL)
    .allowTools('Bash', 'Read', 'Write')
    .skipPermissions()
    .inDirectory(HERE)
    .withTimeout(timeoutMs)
    .withEnv({
      LETTA_BASE_URL,
      MAZDA_AGENT_ID,
      MAZDA_CONVERSATION_ID: args.conversationId,
      MAZDA_TRAINER_REPORT_PATH: args.reportPath,
    })
    .onToolUse((tool) => {
      console.log(`[trainer] tool: ${tool.name} ${JSON.stringify(tool.input).slice(0, 300)}`);
    })
    .query(prompt)
    .asText();
}

async function runCodexAttempt(prompt, timeoutMs, attempt, args) {
  const summaryPath = `/tmp/mazda_trainer_summary_${process.pid}_${attempt}.txt`;
  const proc = Bun.spawn([
    CODEX_BIN, 'exec', '--ephemeral', '--skip-git-repo-check',
    '--dangerously-bypass-approvals-and-sandbox', '--color', 'never',
    '--model', TRAINER_CODEX_MODEL, '--cd', HERE,
    '--output-last-message', summaryPath, '-',
  ], {
    cwd: HERE,
    env: {
      ...process.env,
      LETTA_BASE_URL,
      MAZDA_AGENT_ID,
      MAZDA_CONVERSATION_ID: args.conversationId,
      MAZDA_TRAINER_REPORT_PATH: args.reportPath,
    },
    stdin: 'pipe',
    stdout: 'pipe',
    stderr: 'pipe',
  });
  proc.stdin.write(prompt);
  proc.stdin.end();

  const stdoutPromise = new Response(proc.stdout).text();
  const stderrPromise = new Response(proc.stderr).text();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    proc.kill();
  }, timeoutMs);
  const exitCode = await proc.exited;
  clearTimeout(timer);
  const [stdout, stderr] = await Promise.all([stdoutPromise, stderrPromise]);
  if (stdout) console.log(stdout.trimEnd());
  if (stderr) console.error(stderr.trimEnd());
  if (timedOut) throw new Error(`Codex Trainer timed out after ${timeoutMs}ms`);
  if (exitCode !== 0) throw new Error(`Codex Trainer exited with code ${exitCode}`);
  try { return readFileSync(summaryPath, 'utf8').trim(); }
  catch { return stdout.trim(); }
}

function writeEmergencyReport(args, errors) {
  const path = args.reportPath;
  writeFileSync(path, `# Mazda Trainer Report\n\n` +
    `- **Verdict:** STALLED\n- **Scanner:** ${args.scanner}\n` +
    `- **Document:** ${args.scanPath}\n- **Dispatch:** ${args.dispatchedAt}\n\n` +
    `- **Conversation:** ${args.conversationId}\n\n` +
    `The Trainer failed before it could complete evidence review or coaching. ` +
    `Mazda's intake result must not be treated as verified.\n\n` +
    `## Runner errors\n\n${errors.map((e) => `- ${e}`).join('\n')}\n`);
  return path;
}

async function notifyDashboardStatus(args) {
  let report;
  try { report = readFileSync(args.reportPath, 'utf8'); }
  catch (err) {
    console.error(`[trainer] cannot publish intake status: ${err?.message || err}`);
    return false;
  }
  const match = report.match(/Verdict[^A-Za-z]*(PASS|CORRECTED|FAIL|STALLED)/i);
  const status = (match?.[1] || 'STALLED').toLowerCase();
  const diagnosis = report.match(/## (?:Diagnosis|Wrapper Defect)\s+([\s\S]*?)(?=\n## |$)/i);
  const detail = (diagnosis?.[1] || '').replace(/\s+/g, ' ').trim().slice(0, 1000);
  try {
    const response = await fetch(`${DASHBOARD_BASE_URL}/api/intake-status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status,
        detail,
        scanner: args.scanner,
        document_path: args.scanPath,
        dispatched_at: Number(args.dispatchedAt),
        conversation_id: args.conversationId,
        report_path: args.reportPath,
      }),
    });
    const body = await response.text();
    if (!response.ok || !body.includes('"ok": true')) {
      throw new Error(`HTTP ${response.status}: ${body.slice(0, 300)}`);
    }
    console.log(`[trainer] dashboard intake status published: ${status}`);
    return true;
  } catch (err) {
    console.error(`[trainer] failed to publish dashboard intake status: ${err?.message || err}`);
    return false;
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  args.reportPath = buildReportPath(args);
  console.log(`[trainer] watching Mazda intake run: scanner=${args.scanner} ` +
    `scan=${args.scanPath} dispatched_at=${args.dispatchedAt} ` +
    `conversation=${args.conversationId || '(dry-run)'} ` +
    `model=${TRAINER_MODEL} codex_fallback=${TRAINER_CODEX_MODEL}`);

  const prompt = `${buildSystemMessage()}\n\n---\n\n${buildTaskMessage(args)}`;

  if (args.dryRun) {
    // Verify prompt assembly (instructions + manual + task) without spending a run.
    console.log(`[trainer] dry-run: prompt is ${prompt.length} chars; ` +
      `manual loaded from ${MANUAL_PATH}`);
    console.log(prompt.slice(0, 400));
    console.log('...');
    console.log(prompt.slice(-700));
    return;
  }

  // Watchdog: the model has ended its turn "to wait" despite instructions. The
  // contract's observable outcome is a report file, so retry the whole session
  // (fresh context; the instructions are stateless — everything is re-derived
  // from Mazda's transcript) until one exists or the time budget runs out.
  const REPORTS_DIR = join(HERE, 'reports');
  mkdirSync(REPORTS_DIR, { recursive: true });
  const startMs = Date.now();
  const reportWritten = () => {
    try { return statSync(args.reportPath).mtimeMs >= startMs; }
    catch { return false; }
  };

  const MAX_ATTEMPTS = 3;
  const errors = [];
  // Claude is the primary. A session that ERRORS (quota/auth/crash/timeout)
  // flips all remaining attempts to the codex fallback; a session that merely
  // ends without a report (the "stopped to wait" contract violation) retries
  // on Claude, since the session itself was healthy.
  let useCodex = false;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    const remainingMs = TRAINER_TIMEOUT_MS - (Date.now() - startMs);
    if (remainingMs < 60_000) break;
    const attemptPrompt = attempt === 1 ? prompt : `${prompt}

---

WATCHDOG — attempt ${attempt} of ${MAX_ATTEMPTS}. A previous trainer session for this same
dispatch ended WITHOUT writing a report (it stopped talking to "wait" — a contract
violation). Mazda's run may already be finished: read her transcript as it stands, grade
what actually happened, coach her if warranted, and WRITE THE REPORT FILE only after the
current document is complete or the deadline makes FAIL/STALLED final. Use the exact required
report path already supplied; never invent another filename. If you must wait, use only a
foreground Bash sleep loop.`;

    const attemptTimeoutMs = Math.min(remainingMs, TRAINER_ATTEMPT_TIMEOUT_MS);
    try {
      const summary = useCodex
        ? await runCodexAttempt(attemptPrompt, attemptTimeoutMs, attempt, args)
        : await runClaudeAttempt(attemptPrompt, attemptTimeoutMs, args);
      console.log(`[trainer] attempt ${attempt} (${useCodex ? 'codex' : 'claude'}) summary:\n` + summary);
    } catch (err) {
      // A session that times out or crashes AFTER writing the report still
      // fulfilled the contract — the report is the deliverable, the final
      // summary is garnish. Fall through to the reportWritten() check.
      const backend = useCodex ? 'codex' : 'claude';
      console.error(`[trainer] attempt ${attempt} (${backend}) errored: ${err?.message || err}`);
      errors.push(`attempt ${attempt} (${backend}): ${err?.message || err}`);
      if (!useCodex) {
        useCodex = true;
        console.log(`[trainer] Claude session failed — falling back to codex ` +
          `(${TRAINER_CODEX_MODEL}) for remaining attempts.`);
      }
    }
    if (reportWritten()) {
      await notifyDashboardStatus(args);
      console.log('[trainer] report file written — done.');
      return;
    }
    console.log('[trainer] no report file since dispatch — relaunching (watchdog).');
  }

  if (!reportWritten()) {
    const emergencyPath = writeEmergencyReport(args, errors);
    await notifyDashboardStatus(args);
    console.error(`[trainer] FAILED: session(s) ended without writing a report; ` +
      `emergency report: ${emergencyPath}`);
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(`[trainer] FAILED: ${err?.stack || err}`);
  process.exit(1);
});
