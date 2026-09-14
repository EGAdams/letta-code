# Postgres connection-exhaustion fix — deployed 2026-09-14

Continuation of `handoff_2026_09_14_11_23.md`. Read that first for full incident history if you
need it; this note only covers what changed after it.

## What was deployed

Chose **Option B** from the prior shift's triage report (semaphore-based cap), not Option A
(enable SQLAlchemy pooling) — Option A hit an unresolved SSL-negotiation bug in `db.py`'s
`connect_args`/alembic path last shift (2 failed attempts, one 25x crash loop). Option B keeps
`NullPool` as-is and sidesteps that rabbit hole entirely, per the prior handoff's own
recommendation.

**New file:** `letta/server/db_connection_limiter.py` on `100.80.49.10` (`~/letta-src`) —
a small `ConnectionLimiter` Strategy interface with two implementations:
- `NullConnectionLimiter` — no-op, used when SQLAlchemy pooling is enabled (the pool already
  caps connections, an extra in-process cap would just be redundant backpressure).
- `SemaphoreConnectionLimiter` — wraps `asyncio.Semaphore`, used when `NullPool` is active
  (today's default).

`build_connection_limiter(...)` is the factory that picks between them from `settings`, and is
also what finally wires up `settings.db_max_concurrent_sessions` — that setting existed in
`settings.py:316` but was dead code before this fix (three other places in the codebase,
`mcp_manager.py`, `file_manager.py`, `mcp_server_manager.py`, already work around the same root
bug by forcing sequential writes instead). If unset, the limiter computes a safe per-worker
default itself: `(pg_max_connections - 10 reserved) / uvicorn_workers` — 10 is reserved for the
scheduler's advisory-lock session (one held open per worker, see `scheduler.py`) plus headroom
for migrations/manual `psql`. With the current prod config (`max_connections=100`,
`LETTA_UVICORN_WORKERS=2`) that's **45 concurrent sessions per worker**, 90 total + 10 reserved
= 100, exactly at the Postgres cap with no slack wasted, and it stays correct automatically if
`uvicorn_workers` or Postgres's `max_connections` ever change — no more magic numbers.

**Changed file:** `letta/server/db.py` — `DatabaseRegistry` now takes a `ConnectionLimiter` via
constructor injection (defaults to the factory-built one at module scope), and
`async_session()` wraps the existing session-opening block in `async with
self._connection_limiter.limit():`. No other logic in that function changed — same retry loop,
same cancellation handling.

Backup of the pre-fix `db.py`: `~/letta-src/letta/server/db.py.pre-connection-limiter-20260914`
on `100.80.49.10`.

## Verification done before/after deploy

- Pure-logic unit test run inside `letta-server`'s own venv (`docker exec letta-server python3
  -c '...'`, no DB writes) — confirmed: pooling-enabled → `NullConnectionLimiter`; NullPool +
  no override → computed default of 45; explicit override wins; and an actual `asyncio.gather`
  test proving a 3rd concurrent caller blocks until one of two capacity-holders releases.
- `docker compose -f docker-compose.prod.yml build letta` — clean build, no errors.
- `docker compose -f docker-compose.prod.yml up -d letta` — both uvicorn workers started clean,
  no tracebacks from the new code, watched `docker logs` through the full startup/migration
  window (not just `Health.Status`, which the prior shift found lags real crash state by up to
  a minute).
- Post-deploy: `Health.Status=healthy`, `restarts=0`, `curl :8283/v1/health/` → `{"status":"ok"}`,
  `pg_stat_activity` count sane (1, idle), zero `Database connection error` retry-warning lines
  in the log.
- **Not yet verified under real concurrent load** — this incident was intermittent/recurring
  under moderate load, not something a quiet idle server proves fixed. Watch for
  `TooManyConnectionsError` over the next few days of normal traffic; if the semaphore cap is
  reached under legitimate load (not a leak), you'd see requests queue rather than the
  Postgres-side hard error — check `docker logs` for anything unusual and consider whether 45/
  worker needs tuning (env var `LETTA_DB_MAX_CONCURRENT_SESSIONS` overrides the computed
  default, applies per-worker).

## Outstanding from prior shift, still open

- **Option A (enable pooling) SSL/alembic bug** — not pursued further since B is now live and
  working. If pooling is ever wanted (e.g. for its other benefits beyond the connection cap),
  the unresolved question from last shift still stands: does `alembic/env.py` call
  `get_database_uri_for_context()` or build its own engine URL separately? Not re-investigated
  this shift.
- **`RuntimeError: generator didn't stop after athrow()` in `db.py`'s `async_session()`** —
  real defect, independent of which fix path is chosen (a connection error should not surface
  as a mismatched generator-close error). **Escalation to Suzuki attempted this shift and
  failed** — Suzuki's Anthropic BYOK provider key is still broken (`llm_bad_request`, "Third-
  party apps now draw from your extra usage, not your plan limits" — same failure as
  `suzuki_broken_anthropic_byok_provider_2026_08_27` memory). Per that memory, the fix is
  switching Suzuki to Codex OAuth, which is EG's call, not something to do unattended. **Next
  shift: re-send this report to Suzuki once its provider is fixed**, or file it by hand if
  Suzuki stays down. Report text is in this session's transcript / git history of this file.

## Rollback if this regresses

```bash
ssh adamsl@100.80.49.10
cd ~/letta-src
cp letta/server/db.py.pre-connection-limiter-20260914 letta/server/db.py
rm letta/server/db_connection_limiter.py
docker compose -f docker-compose.prod.yml build letta
docker compose -f docker-compose.prod.yml up -d letta
```
