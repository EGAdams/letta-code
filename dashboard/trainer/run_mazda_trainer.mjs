#!/usr/bin/env bun
// Mazda Trainer — dynamically builds a Claude agent (via claude-code-sdk-ts) that
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

import { readFileSync } from 'node:fs';
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
const MAZDA_AGENT_ID =
  process.env.MAZDA_AGENT_ID || 'agent-6b536cf4-ec88-4290-b595-fed21d14bd8e';
const TRAINER_MODEL = process.env.TRAINER_MODEL || 'sonnet';
const TRAINER_TIMEOUT_MS = Number(process.env.TRAINER_TIMEOUT_MS || 25 * 60 * 1000);

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

  const summary = await claude()
    .withModel(TRAINER_MODEL)
    .allowTools('Bash', 'Read', 'Write')
    .skipPermissions()
    .inDirectory(HERE)
    .withTimeout(TRAINER_TIMEOUT_MS)
    .withEnv({ LETTA_BASE_URL, MAZDA_AGENT_ID })
    .onToolUse((tool) => {
      console.log(`[trainer] tool: ${tool.name} ${JSON.stringify(tool.input).slice(0, 300)}`);
    })
    .query(prompt)
    .asText();

  console.log('[trainer] final summary:\n' + summary);
}

main().catch((err) => {
  console.error(`[trainer] FAILED: ${err?.stack || err}`);
  process.exit(1);
});
