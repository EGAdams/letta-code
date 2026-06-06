# Scissari `executor_run` Stall — Divide & Conquer Fix

Scaffold for the redesign described in
[`../divide_and_conquer_scissari_fix.html`](../divide_and_conquer_scissari_fix.html).

Replaces the blind **14-call retry loop** (which resets Scissari's conversation
with *"No specific tool error captured"*) with a classified, strategy-driven
recovery pipeline built from GoF patterns.

## Why this exists

`executor_run` fails in **six structurally different ways** (F1–F6), but the
current loop guard retries all of them identically until a dumb counter hits 14
and nukes the conversation. The fix: **classify the failure**, then let a
Strategy chosen from the classification decide whether to retry, narrow, fall
back, or abort — with a Circuit Breaker and an explicit State machine making
"14" obsolete and a Memento making every reset explain itself.

| # | Failure | Kind | Correct response |
|---|---------|------|------------------|
| F1 | HTTP 400 allowlist | `ALLOWLIST_BLOCKED` | abort fast (never retry) |
| F2 | HTTP 500 watchfiles reload | `SERVER_RELOAD_500` | backoff + ≤2 retries |
| F3 | HTTP 408 timeout | `REQUEST_TIMEOUT` | narrow the command |
| F4 | ECONNREFUSED | `EXECUTOR_DOWN` | circuit-open + alert |
| F5 | `end_turn` w/o `tool_return` | `END_TURN_NO_RETURN` | client-side fallback |
| F6 | peer `max_steps` (bad tool rule) | `PEER_TOOL_RULE_HANG` | detect & abort |

## Layout

```
scissari_executor/
  models.py        # Command + value objects + enums (Pydantic)
  interfaces.py    # ABC ports — program to THESE
  strategies.py    # Strategy + Template Method (one per FailureKind)
  classifiers.py   # Chain of Responsibility (F1..F6 fingerprints)
  guard.py         # State machine + per-kind budgets + Memento
  breaker.py       # Circuit breaker — kills the 14x spin
  service.py       # Facade — the only entry point Scissari calls
tests/
  test_classifier.py       # six real failure fixtures
  test_loop_guard.py       # trips at budget (2), NOT 14
  test_circuit_breaker.py
  test_service_facade.py    # asserts the old "no error" lie is gone
  fakes.py
```

## Status: GREEN ✅

All modules are implemented and the suite passes (**16 passed**). The scaffold
started red-by-construction (every method a `NotImplementedError` stub) and was
turned green one module at a time in the build order below.

```bash
cd scissari-executor-fix
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q          # 16 passed
```

Build order followed (HTML section 6): models → classifiers → breaker →
strategies → guard → facade. To see the original red phase, `git stash` the
implementations or revert any one module's body back to `raise NotImplementedError`.

### Test coverage

| Test file | Proves |
|-----------|--------|
| `test_classifier.py` | each of F1–F6 is classified with a concrete reason; unknown → ABORT |
| `test_circuit_breaker.py` | opens after 2 EXECUTOR_DOWN; a success resets it |
| `test_loop_guard.py` | trips at the per-kind budget (2), **not 14**; ABORT trips immediately; captures a Memento |
| `test_service_facade.py` | dead executor / allowlist abort after **1** call and alert with a real reason |
| `test_recovery_paths.py` | healthy call returns with no alert; a transient 500 retries **once** then succeeds |

## Wiring into lettabot (the remaining step)

The live `count < 14` loop and the Telegram alert live in **lettabot** on Win11
(`100.72.158.63:/home/adamsl/lettabot`), which is not mounted in this WSL. To
adopt this subsystem there:

1. Copy `scissari_executor/` into the lettabot Python tree (or `pip install -e`
   this folder).
2. Construct one `ExecutorRunService` at startup, injecting:
   - an `IExecutorClient` adapter around the real HTTP executor (`127.0.0.1:8787`),
   - `IAlertSink` implementations for Telegram + `~/.letta/scissari-alerts.jsonl` + the dashboard LED,
   - a real `IConversationSnapshotStore` (write the transcript snapshot to disk).
3. Replace the blind retry loop with `await service.execute(cmd, agent_id)`.
4. On `StalledError`, send `err.report.message` to Telegram — it now names the
   failure kind and evidence instead of *"No specific tool error captured."*

## Cross-references (letta-code)

- `src/tools/toolset.ts` — `findHangingToolRules()` (F6 detector)
- `src/agent/multi-agent-tool-fallback.ts` — `CLIENT_SIDE_FALLBACK_TOOLS` (F5)
- `src/skills/custom/debugging-executor-run/SKILL.md` — F1–F4 fingerprints
- `src/integration-tests/agent-tool-rule-audit.integration.test.ts` — live F6 guard
