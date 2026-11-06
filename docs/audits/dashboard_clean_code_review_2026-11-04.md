# Dashboard clean-code review — 2026-11-04

## Scope and preservation

This was a read-only review of the dashboard plus creation of this document and the companion checklist. I inspected `dashboard/server.py`, `dashboard/agents/registry.py`, `dashboard/agents/model_options.py`, `dashboard/js/dashboard-boot.js`, `dashboard/js/boot/agent-manager.js`, `dashboard/js/abstract/chatgpt-provider-account-controller.interface.js`, `dashboard/js/implementation/chatgpt-provider-account-panel.js`, selected tests, and the dashboard markup. The working tree already contained concurrent Claude changes to dashboard HTML, CSS, route modules, JS modules/tests, a database, and new files; I did not edit or overwrite any of those files.

The repository instructions referenced `/home/adamsl/.claude/.../MEMORY.md` and `/home/adamsl/.letta/skills/chipping-away-at-server-rewrite/SKILL.md`; both paths were unavailable, so no claims are made from those sources. No network, deployment, commit, reset, checkout, clean, stash, or application-code edit was performed.

## Findings

### SOLID and separation of concerns

- Positive: `dashboard/js/dashboard-boot.js:16-54,110-167` is a composition root that constructs injected collaborators and section factories. `dashboard/js/boot/agent-manager.js:15-35` receives its dependencies rather than importing browser/network singletons directly.
- Positive: `dashboard/agents/model_options.py:36-94` isolates model-option policy behind `AgentModelOptionsService` and an `ILettaGateway`; `dashboard/agents/registry.py:32-167` uses typed boundary models and validators for roster/card/voice data.
- Risk: `dashboard/server.py` is 4,507 lines (measured with `wc -l`) and still contains finance, intake, scanner, voice, agent, health, provider, and HTTP composition responsibilities. This is a maintainability and single-responsibility concern, even though some extractions are already visible at the import boundary (`server.py:24-26,39-140`).
- Risk: the server retains compatibility/re-export wrappers and late-bound globals. Those can protect tests and monkeypatching, but they also preserve coupling; each future extraction should remove a caller dependency rather than add another wrapper.

### Duplicate logic and data drift

- Positive: `dashboard/agents/registry.py:262-280` rejects duplicate roster names and IDs, and `dashboard/tests/test_agents_registry.py:93-105,118-130` covers the duplicate-tile regression.
- Positive: `dashboard/agents/model_options.py:59-89` handles provider suffixes and explicit family overrides in one policy location; `dashboard/tests/test_model_options.py:28-52` exercises those cases.
- Remaining concern: `dashboard/server.py:205-209` explicitly documents cross-language duplication: month keys, scanner keys, and the Mazda agent ID are also hard-coded in JavaScript. This is a concrete source-of-drift item, not an inferred defect.
- Remaining concern: `dashboard/js/boot/agent-manager.js:86-103` and `:171-180` have separate roster-fetch paths; the deep-link path silently ignores a failed fetch (`catch (_e) {}`). They may be intentionally different, but the failure policy and cache ownership should be made explicit.

### Error handling

- Positive: `dashboard/js/boot/agent-manager.js:94-101` reports roster-fetch failures to the gate and status element; `dashboard/js/implementation/agent-health-poller.js:27` catches poll failures rather than allowing a timer callback to throw.
- Concern: `dashboard/server.py` contains many broad catches, including examples at lines 626, 1142, 2497, 3097, 3130, 3159, 3197, 3251, 3288, 3319, 3336, 3385, 3414, 3634, and 3665. Some may be deliberate fail-safe behavior, but the review did not verify logging or user-visible semantics for each. They are an audit queue, not confirmed bugs.
- Concern: `dashboard/server.py:3657-3665` catches all exceptions in `letta_get` and returns `None`; callers need a reliable distinction between not-found, unavailable, malformed response, and empty data.

### Accessibility

- Positive source evidence: `dashboard/dashboard.html:634-650` uses dialog semantics and labelled-by relationships; `dashboard/dashboard.html:499-507` uses live status and an accessible close label; `dashboard/js/abstract/agent-bridge-poll-form.js:52-64` provides labels/ARIA names for generated fields; `dashboard/js/abstract/worker-activity-render.js:71-85` uses a log role and live output.
- Unchecked: no browser, keyboard, screen-reader, focus-trap, contrast, zoom, or reduced-motion verification was performed. Static presence of ARIA attributes does not prove accessible behavior.
- Follow-up: generated markup in `dashboard/js/boot/server-manager.js:166-172` and `dashboard/js/boot/ssh-manager.js:118-120` includes filter inputs; their accessible naming and focus behavior need a browser check.

### Provider selection, address, and refresh

- Provider selection: `dashboard/agents/model_options.py:61-89` infers a family from the live provider and preserves a current model when it has no catalog match. This is covered by `test_model_options.py`, but broader malformed-provider and save/reload cases remain unchecked.
- Provider account refresh/set: `dashboard/js/abstract/chatgpt-provider-account-controller.interface.js:49-86` starts an immediate refresh, schedules a 60-second poll, and has separate refresh/set error paths. `dashboard/js/dashboard-boot.js:124-128` mounts the concrete DOM adapter. I did not verify overlapping set/refresh responses or browser feedback under a real HTTP failure.
- Address: `dashboard/server.py:2734-2749` imports `LETTA_BASE_URL` and constructs the gateway from it. `dashboard/js/boot/agent-manager.js:77-82` embeds `http://100.80.49.10:8765/` in file-mode guidance. That user-facing fallback can diverge from deployment configuration and should be centralized or clearly marked as an operator hint.
- Refresh/cache: `dashboard/server.py:2849-2868` defines roster and activity caches; `dashboard/server.py:4297` exposes `build_agent_list(force_refresh=False)`, while `dashboard/js/boot/agent-manager.js:86-103` caches agents for the browser lifetime. The review did not find a complete, tested contract for when a user-visible refresh should invalidate both layers.

## Checks run and results

- `wc -l dashboard/server.py` — completed: 4,507 lines.
- Read-only searches and numbered source inspection across the files named above — completed.
- Attempted focused pytest command with `tests/test_agents_registry.py`, `tests/test_model_options.py`, `tests/test_chatgpt_provider_status.py`, and a mistakenly named `tests/test_oauth_account.py` — no tests ran because that path does not exist.
- Corrected focused pytest command — blocked during collection by `ModuleNotFoundError: No module named 'adw_modules'` while importing `server.py` through `receptionist_work`.
- Attempted JavaScript focused tests — blocked because `bun` is not installed/in PATH (`/bin/bash: bun: command not found`).

## Remaining unchecked areas

The full Python suite, JavaScript suite, HTTP route inventory, live-provider/account behavior, real address switching, browser accessibility, performance under concurrent polling, security review of all static/path inputs, and deployment behavior were not verified. No conclusion about those areas should be inferred from this audit.
