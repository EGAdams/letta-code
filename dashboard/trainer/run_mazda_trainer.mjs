#!/usr/bin/env bun
// Mazda Trainer — dynamically builds a Codex agent that
// watches ONE Mazda intake run, verifies it, and coaches Mazda on failures.
//
// Fired fire-and-forget by dashboard/server.py (_notify_trainer_of_scan) every time
// a scan is dispatched to Mazda. Can also be run by hand:
//
//   bun run_mazda_trainer.mjs --scan-path /path/on/executor/scan.jpg \
//       --scanner "Window Scanner" --facade '{"ok":true,...}' --dispatched-at 1752170000
//
// The agent's system message = mazda_trainer_instructions.md + the text of
// notes_plans_handoffs/mazda_dev_status.html (Mazda's developer manual).

import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

const INSTRUCTIONS_PATH = join(HERE, 'mazda_trainer_instructions.md');
const MANUAL_PATH = join(HERE, '..', '..', 'notes_plans_handoffs', 'mazda_dev_status.html');

const LETTA_BASE_URL = process.env.LETTA_BASE_URL || 'http://100.80.49.10:8283';
const MAZDA_AGENT_ID =
  process.env.MAZDA_AGENT_ID || 'agent-6b536cf4-ec88-4290-b595-fed21d14bd8e';
const TRAINER_MODEL = process.env.TRAINER_MODEL || 'gpt-5.6-sol';
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
    else if (key === '--dry-run') args.dryRun = true;
  }
  if (!args.scanPath || !args.scanner) {
    console.error('Usage: run_mazda_trainer.mjs --scan-path <path> --scanner <name> ' +
      '[--facade <json>] [--dispatched-at <unix ts>]');
    process.exit(2);
  }
  if (!args.dispatchedAt) args.dispatchedAt = String(Math.floor(Date.now() / 1000));
  return args;
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
    `Deterministic facade result: ${args.facade}`,
    '',
    'Environment values for your curl commands:',
    `  LETTA_BASE_URL=${LETTA_BASE_URL}`,
    `  MAZDA_AGENT_ID=${MAZDA_AGENT_ID}`,
  ].join('\n');
}

async function runCodexAttempt(prompt, timeoutMs, attempt) {
  const summaryPath = `/tmp/mazda_trainer_summary_${process.pid}_${attempt}.txt`;
  const proc = Bun.spawn([
    CODEX_BIN, 'exec', '--ephemeral', '--skip-git-repo-check',
    '--dangerously-bypass-approvals-and-sandbox', '--color', 'never',
    '--model', TRAINER_MODEL, '--cd', HERE,
    '--output-last-message', summaryPath, '-',
  ], {
    cwd: HERE,
    env: { ...process.env, LETTA_BASE_URL, MAZDA_AGENT_ID },
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
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace('T', '-').slice(0, 15);
  const scanner = args.scanner.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
  const path = join(HERE, 'reports', `${stamp}_${scanner || 'scanner'}.md`);
  writeFileSync(path, `# Mazda Trainer Report\n\n` +
    `- **Verdict:** STALLED\n- **Scanner:** ${args.scanner}\n` +
    `- **Document:** ${args.scanPath}\n- **Dispatch:** ${args.dispatchedAt}\n\n` +
    `The Codex Trainer failed before it could complete evidence review or coaching. ` +
    `Mazda's intake result must not be treated as verified.\n\n` +
    `## Runner errors\n\n${errors.map((e) => `- ${e}`).join('\n')}\n`);
  return path;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  console.log(`[trainer] watching Mazda intake run: scanner=${args.scanner} ` +
    `scan=${args.scanPath} dispatched_at=${args.dispatchedAt} model=${TRAINER_MODEL}`);

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
    try {
      return readdirSync(REPORTS_DIR).some((f) => {
        try { return statSync(join(REPORTS_DIR, f)).mtimeMs >= startMs; }
        catch { return false; }
      });
    } catch { return false; }
  };

  const MAX_ATTEMPTS = 3;
  const errors = [];
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    const remainingMs = TRAINER_TIMEOUT_MS - (Date.now() - startMs);
    if (remainingMs < 60_000) break;
    const attemptPrompt = attempt === 1 ? prompt : `${prompt}

---

WATCHDOG — attempt ${attempt} of ${MAX_ATTEMPTS}. A previous trainer session for this same
dispatch ended WITHOUT writing a report (it stopped talking to "wait" — a contract
violation). Mazda's run may already be finished: read her transcript as it stands, grade
what actually happened, coach her if warranted, and WRITE THE REPORT FILE — do it EARLY,
as soon as you have a verdict, before any optional polish. Write to a NEW filename using
the current UTC timestamp; never overwrite a previous attempt's file. If you must wait,
use only a foreground Bash sleep loop.`;

    try {
      const summary = await runCodexAttempt(
        attemptPrompt, Math.min(remainingMs, TRAINER_ATTEMPT_TIMEOUT_MS), attempt);
      console.log(`[trainer] attempt ${attempt} summary:\n` + summary);
    } catch (err) {
      // A session that times out or crashes AFTER writing the report still
      // fulfilled the contract — the report is the deliverable, the final
      // summary is garnish. Fall through to the reportWritten() check.
      console.error(`[trainer] attempt ${attempt} errored: ${err?.message || err}`);
      errors.push(`attempt ${attempt}: ${err?.message || err}`);
    }
    if (reportWritten()) {
      console.log('[trainer] report file written — done.');
      return;
    }
    console.log('[trainer] no report file since dispatch — relaunching (watchdog).');
  }

  if (!reportWritten()) {
    const emergencyPath = writeEmergencyReport(args, errors);
    console.error(`[trainer] FAILED: session(s) ended without writing a report; ` +
      `emergency report: ${emergencyPath}`);
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(`[trainer] FAILED: ${err?.stack || err}`);
  process.exit(1);
});
