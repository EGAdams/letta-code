# Postgres/letta-server triage agent — blueprint

Reusable recipe for spinning up an Opus-model Claude SDK agent to triage a
`letta-server` incident (first used 2026-09-14 for `asyncpg.exceptions.TooManyConnectionsError:
sorry, too many clients already`, a **recurring** issue). Use this whenever `letta-server`
goes unhealthy in a way a simple restart doesn't durably fix, and the cause needs real
investigation in the Letta source, not just a container bounce.

## Why this exists

Restarting `letta-server` clears the symptom but not the cause, and the person doing the
restart is rarely the person who can read the SQLAlchemy pool config and the actual server
source at the same time as the live docker state. This blueprint hands that investigation to
an Opus agent with real read access to the source, while keeping it unable to damage
production by accident.

## The tool: `run_claude_code_sdk` / `/claude_sdk`

Mazda's `run_claude_code_sdk` Letta tool and this same HTTP endpoint are backed by the
**SDK-equipped executor** on the Win10/WSL box — see `claude_sdk_executor_8799` memory for
the full backstory (ghost-vs-duplicate-stack history, token sync cron, etc). Call it directly
when you don't want to go through a Letta agent turn:

```bash
curl -s -m 600 -X POST http://100.80.49.10:8799/claude_sdk \
  -H "Authorization: Bearer frita-win10-exec-7b3c1f9a8d2e4f60" \
  -H "Content-Type: application/json" \
  --data @request.json
```

Request schema (`ClaudeSdkRequest` in `~/server_tools/executor_server.py`):

```json
{
  "task": "the full prompt, including your system-prompt preamble — there is no separate system-prompt field",
  "context": "optional extra context appended after the task",
  "working_dir": "/work",
  "model": "opus"
}
```

`model` is regex-validated: `haiku|sonnet|opus|claude-*`. Model policy for this deployment:
**haiku = cheap/simple, sonnet = default, opus = only when stuck / a real investigation** (per
`mazda_team_agents_memory`). A Postgres connection-exhaustion root-cause hunt qualifies as
opus-tier.

Health check before calling (see `claude_sdk_executor_8799` memory):
```bash
curl -s -m8 -o /dev/null -w "%{http_code}" http://100.80.49.10:8799/                    # 405 = up
curl -s -m8 -o /dev/null -w "%{http_code}" -X POST http://100.80.49.10:8799/claude_sdk  # 422 = up
```

## Critical constraint: the executor sandbox is NOT the host

`frita-executor` (the container backing `:8799`) is a **shared, always-on container** other
tasks (Mazda's minions, rol_finances work) also run in. It has:
- **No `docker` CLI, no `ssh`** — it cannot run `docker exec`, restart anything, or reach
  Postgres live. It only sees what's mounted into it, or what you paste into `task`/`context`.
- Its own writable scratch space at **`/work`** (host volume `frita_work`) — this is the ONLY
  place the agent should write output. Never point `working_dir` at a repo you don't want
  touched.
- As of 2026-09-14, **`/home/adamsl/letta-src` (the real Letta server source) is mounted
  READ-ONLY** at that same path — added specifically so a triage agent can read `db.py`,
  `settings.py`, `docker-compose.prod.yml`, etc. directly instead of a human hand-copying
  snippets into `context` every time. Verified read-only:
  `docker exec frita-executor sh -c 'touch /home/adamsl/letta-src/x'` → `Read-only file system`.
  If this mount is ever missing (e.g. after a `deploy_frita_executor.sh` script gets
  reverted), re-add the line
  `-v /home/adamsl/letta-src:/home/adamsl/letta-src:ro \` to BOTH the `docker run` and the
  `docker create` fallback blocks in `~/server_tools/deploy_frita_executor.sh`, then
  `bash ~/server_tools/deploy_frita_executor.sh` to redeploy.
- Also mounted (read-write, unrelated repos, generally irrelevant to this task):
  `/home/adamsl/letta-code`, `/home/adamsl/rol_finances`, `/home/adamsl/claude-code-sdk-ts`,
  `/home/adamsl/frita-claude-home`, `/var/www/html`.

**Why read-only, not read-write:** researched current (2026) agentic-sandbox practice
(Northflank/NVIDIA/Cosmonic guidance) — least privilege, explicit workspace boundaries. A
shared always-on container should never get standing write access to production source; a
bad agent run could corrupt it and every OTHER task sharing that container inherits the risk.
Read-only gets the agent real exploration without that blast radius. Any actual code fix the
agent proposes goes out as a **diff in its `/work` report**, applied by a human (or a
deliberately-scoped separate step) — not auto-applied by the sandboxed agent itself.

## Keep Opus's context lean: windowed reads, not whole-file `cat`

Large files (server source, docker logs, postgresql.conf) will blow Opus's context if it
`cat`s them whole. Ship it a small helper script and instruct it to use that instead of raw
`cat`. Copy this into the executor's `/work` before calling `/claude_sdk` (it persists across
calls since `/work` is a named volume):

```bash
scp read_helpers.sh adamsl@100.80.49.10:/tmp/read_helpers.sh
ssh adamsl@100.80.49.10 \
  "docker exec -i frita-executor sh -c 'cat > /work/read_helpers.sh' < /tmp/read_helpers.sh"
```

`read_helpers.sh` contents:

```bash
#!/usr/bin/env bash
# Windowed-reading helpers — use these instead of `cat` on any file over ~200 lines.
# Source this file first: `source /work/read_helpers.sh`

# read_window <file> <start_line> <end_line>
read_window() { sed -n "${2},${3}p" "$1"; }

# grep_context <pattern> <file> [context_lines=5]
grep_context() { grep -n -B "${3:-5}" -A "${3:-5}" -- "$1" "$2"; }

# find_def <symbol> <file_or_glob>   — jump straight to a function/class/const definition
find_def() { grep -n -E "(def |class |const |function |=>).*$1" $2; }

# tail_lines <file> <n=100>
tail_lines() { tail -n "${2:-100}" "$1"; }

# head_lines <file> <n=100>
head_lines() { head -n "${2:-100}" "$1"; }

# count_lines <file>  — check size before deciding how to read it
count_lines() { wc -l < "$1"; }
```

Include this instruction near the top of the `task` prompt:

> Before reading any file over ~200 lines, run `wc -l <file>` first, then use the windowed-read
> helpers at `/work/read_helpers.sh` (source it: `source /work/read_helpers.sh`) —
> `read_window`, `grep_context`, `find_def`, `tail_lines`, `head_lines`. Do NOT `cat` large
> files whole. Prefer `grep -n` to locate line numbers, then `read_window` around them.

**IMPORTANT note for the next person using this blueprint (NOT yet verified as of
2026-09-14):** the Claude Code SDK's `Bash` tool may or may not persist shell state (sourced
functions) across separate tool calls within one SDK run. If sourcing doesn't stick, fall back
to instructing the agent to call the helpers inline every time, e.g.
`sed -n '100,160p' /path/to/file` directly, without relying on `source`. Confirm which is true
next time this is run and update this note.

## System-prompt / task template

Since `/claude_sdk` has no separate system-prompt field, put the persona + constraints at the
top of `task` itself. Skeleton (fill in the `KNOWN FACTS` section with whatever you've already
diagnosed by hand — give the agent a head start, don't make it re-derive things you already
know):

```
SYSTEM PROMPT: You are a <domain> triage specialist for <system>. This is a RECURRING
incident — find the actual root cause, not just <the standard workaround>.

ENVIRONMENT CONSTRAINTS (read first):
- You are running inside the `frita-executor` sandbox, not the host.
- <list what's mounted read-only, read-write, and what's NOT reachable — no docker/ssh, etc.>
- <windowed-read instruction from above>

KNOWN FACTS (already gathered, do not re-derive):
- <symptom, exact error text, relevant config values, relevant source-file locations>

YOUR TASK:
1..N. <concrete investigation steps>
Produce a written report at /work/<name>_report.md containing: root cause with file:line
citations, a concrete fix (env/config change or a unified diff you can't apply directly),
an immediate remediation recipe (exact commands a human with docker access can run right
now), and a prevention/monitoring suggestion.

Be skeptical of your own first hypothesis — if the numbers don't clearly explain the
symptom, say so explicitly and keep looking rather than reporting an inconclusive guess.
```

## Retrieving the result

The agent writes its report into `/work` inside the container, which is also the host-side
named volume `frita_work`. Pull it out over SSH (no docker CLI needed on your end if you're
SSHing into the Win10/WSL box itself, which does have docker):

```bash
ssh adamsl@100.80.49.10 "docker exec frita-executor cat /work/<name>_report.md"
```

The synchronous `/claude_sdk` HTTP response itself also contains the agent's final text
output (`{"status": "...", "output": "..."}`) — but treat the `/work` file as the source of
truth for anything long, since the HTTP response can be truncated/summarized by the SDK
wrapper.

## First real run (2026-09-14)

Task: diagnose `asyncpg.exceptions.TooManyConnectionsError: sorry, too many clients already`
on `letta-server` (embedded Postgres, `max_connections=100`, `pg_pool_size=25` /
`pg_max_overflow=10` per worker, `LETTA_UVICORN_WORKERS=2` in
`docker-compose.prod.yml` — pool math alone (≤70) doesn't obviously exceed 100, so the agent
was told explicitly to be skeptical of a too-easy answer and look for a leak instead — e.g.
in `letta/server/db.py`'s `async_session()` exception/cancellation handling, or a second
engine/connection path elsewhere in `letta-src/letta`).

**Outcome (real root cause, high confidence):** the pool-size math was a red herring —
`letta/settings.py:315` has `disable_sqlalchemy_pooling: bool = True` as the DEFAULT, which
forces SQLAlchemy's `NullPool` (`db.py:30-31`), so `pg_pool_size`/`pg_max_overflow` are silently
ignored and **every DB operation opens a brand-new Postgres connection with no app-level cap**.
A related setting `db_max_concurrent_sessions` exists (`settings.py:316`) but is defined and
never wired up. The codebase has three separate comments elsewhere (`mcp_manager.py:501`,
`file_manager.py:464`, `mcp_server_manager.py:625`) working around this exact problem by
forcing sequential (not concurrent) DB writes — i.e. Letta's own developers already hit this and
patched around it piecemeal instead of fixing the pool config. Recommended immediate fix (no
code change): set `LETTA_DISABLE_SQLALCHEMY_POOLING=false`, `LETTA_PG_POOL_SIZE=20`,
`LETTA_PG_MAX_OVERFLOW=5` as env vars on the `letta` service in `docker-compose.prod.yml` (50
connections across 2 workers, well under the 100 cap). Full report with a code-patch option
(semaphore-based) and a monitoring script: pulled from `/work/postgres_triage_report.md` inside
`frita-executor` — copy it out via
`ssh adamsl@100.80.49.10 "docker exec frita-executor cat /work/postgres_triage_report.md"`
before it's overwritten by a future run of this same blueprint (nothing rotates `/work`
automatically).
