# Dashboard clean-code checklist — 2026-11-04

This is a prioritized, evidence-based follow-up list from the companion review. It is a review checklist, not an implementation record.

## P0 — protect behavior while reducing coupling

- [ ] Preserve the current composition-root boundary in `dashboard/js/dashboard-boot.js`; keep new section behavior in `dashboard/js/boot/` and reusable browser-independent rules in `dashboard/js/abstract/` or `dashboard/js/implementation/`.
- [ ] Reduce `dashboard/server.py` from its observed 4,507-line composition/service file by one real responsibility seam at a time. Before each slice, identify its interface, adapter, tests, and deletion target; do not move code only to improve the line count.
- [ ] Add an offline test environment or documented dependency setup so dashboard tests can import the application without the missing `adw_modules` package. The attempted focused run failed during collection for that reason.
- [ ] Add route-level tests for provider selection, address/base-URL behavior, and explicit refresh semantics, including stale-cache and failed-upstream cases.

## P1 — provider, address, and refresh correctness

- [ ] Define one typed source of truth for the dashboard/Letta address and document which values may come from `hosts.LETTA_BASE_URL`, request hosts, or hard-coded user-facing help text. `dashboard/js/boot/agent-manager.js` currently embeds a Tailscale address in its `file://` guidance while the backend imports `LETTA_BASE_URL` from `hosts.py`.
- [ ] Separate provider identity, model-family filtering, and account-token installation into explicit ports/services. Review the prefix inference in `dashboard/agents/model_options.py` against provider names with suffixes and against unknown model handles.
- [ ] Specify refresh ownership: roster cache (`AGENT_LIST_CACHE_TTL`), browser-local agent cache, provider-account polling, and health pollers currently have different lifetimes. Add tests that prove refresh invalidates or intentionally preserves each cache.
- [ ] Make concurrent refresh/set operations visibly serialized or stale-result-safe in the provider account controller; retain the existing failure rendering and add tests for overlapping requests.

## P1 — error handling and data boundaries

- [ ] Inventory broad `except Exception` and silent fallback paths in `dashboard/server.py`; replace each with a narrow exception policy, structured logging/correlation, and a user-safe error response where appropriate.
- [ ] Keep all browser-rendered untrusted values escaped. Review every `innerHTML` producer in the active `dashboard/js/` tree, especially status/error strings and dynamically generated controls, and add regression tests for hostile names/messages.
- [ ] Validate every HTTP boundary with the existing Pydantic/request models or equivalent runtime validation, including provider/account payloads and refresh query parameters.

## P2 — accessibility and maintainability

- [ ] Run an actual browser accessibility pass (keyboard order, focus return, dialog focus trap, screen-reader announcements, contrast, and reduced motion). The source inspection found several positive `aria-live`, `aria-label`, and dialog attributes but cannot establish usable interaction behavior.
- [ ] Add accessible names to dynamically generated inputs and filters where labels are currently placeholders or implicit; verify generated buttons have stable names and focus styles.
- [ ] Remove or quarantine stale baseline/backup copies from the active review surface, or document why they remain. The repository contains multiple `dashboard-boot` and `server.py` backups that increase search ambiguity.
- [ ] Measure duplicate route/poll/render logic after the current concurrent work settles; do not deduplicate against files that are actively being edited by Claude.

## Verification checklist for the next slice

- [ ] Record the exact files and working-tree state before editing; preserve simultaneous Claude changes.
- [ ] Add or update focused tests before implementation where the behavior is currently implicit.
- [ ] Run the focused Python suite and the JavaScript suite in an environment with their declared dependencies.
- [ ] Run the dashboard full test suite, then manually verify provider selection, agent address/deep-link loading, refresh, failure display, and keyboard access in a browser.
- [ ] Re-check `git status`; confirm only the intended application slice and its tests changed. Do not deploy or commit as part of this audit.
