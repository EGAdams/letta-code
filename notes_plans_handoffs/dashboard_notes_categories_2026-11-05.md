# Dashboard Notes — 10-Category Staging (2026-11-05)

**Status: NOT applied to the live dashboard. Staged content only.** See "Blocker" below
before assuming any of this exists in the live Notes tab yet.

## Addendum (2026-11-05, later same day): accordion UI landed, code-only

A follow-up task ("use the accordion style we're using for the logs") added code that
groups the Notes list into 10 collapsible `<details>` categories by filename, in
`dashboard/js/boot/notes.js` (see `dashboard/docs/notes.md` for the convention). That
code is **unverified on the live dashboard** — same sandbox, same blocker as below — and
contains **no new starter notes**; the 10 drafts in this file are still the only staged
content and still need the manual paste-in described under "How to apply this." One
detail matters for that step: **type the title exactly as shown below** (e.g.
`01. Scoreboard Development`) — the accordion code detects a category only from the
`01-`…`10-` token that name slugifies into, nothing else, so an exact match is what puts
the note under its intended heading instead of "All other notes."

## Blocker — why this could not be written to live Notes

This task ran in a sandboxed `letta-code` checkout with no command execution and no
network/filesystem access outside this repo directory. Two independent things stop a new
note from reaching the live dashboard from here, not just one:

1. **No path to `NOTES_DIR`.** The Notes tab stores Markdown files in `NOTES_DIR`
   (default `~/notes`, see `dashboard/voice/config.py:47` and `dashboard/docs/notes.md`).
   That directory is outside this repo, on whichever host is actually serving the dashboard
   (per `dashboard/CLAUDE.md`, often *not* the box a given checkout is sitting on). This
   sandbox has no `~/notes` directory and no way to SSH, call `/api/note-save`, or restart
   the service — so nothing could be verified live even if a write were attempted.
2. **The ChatGPT-facing bridge refuses creation by design, independent of sandboxing.**
   `notes_bridge.py` / `/api/notes-bridge/v1` (the one channel an agent like me is actually
   meant to use against production) is explicitly **read/update of pre-approved notes
   only** — see `dashboard/docs/notes.md`: *"No create. The façade reads and updates
   existing approved notes; it never makes a new file, so there is no duplicate copy to
   drift."* That is a deliberate safety boundary against exactly this kind of
   automated mass note creation, and this task does not attempt to route around it.
   A human using the dashboard's own **Notes → New note** button is not subject to that
   restriction — `/api/note-save` has no such limit — so the ten notes below are written
   to be pasted there directly, not something that requires loosening the bridge.

**Net effect:** no note was created, edited, reordered, or deleted in live storage. The
**Personal Representative's Deed** note was not opened, read, or touched in any way — this
task never had a path to it. No code was changed (none was needed — see "Why no code
change" below). No deploy, commit, or push happened.

## Duplicate check against the queued task

I searched this checkout for task id `t_ef0ad135cf930cae314baa7a` and for the title
*"Project Organization Brainstorm — Department / Project / Task (2026-11-05)"* — neither
appears anywhere in `letta-code` (code, docs, or `notes_plans_handoffs/`). That is expected:
if that task already ran, its output would be a live note in `~/notes`, which this
checkout cannot see. **Before creating anything from this file, check the live Notes list
for that exact title first.** If it exists:
- Reuse it as the overview/navigator note instead of creating a new one (see the overview
  draft below — merge into the existing note rather than duplicating it).
- Still create the 10 category notes below; that task was scoped to one summary note, not
  the ten categories.

If it does not exist yet, create the overview note from the draft below, and if the other
task runs later and finds this one, it should do the same merge in reverse.

## Why no code change

Checked `dashboard/voice/note_models.py` (`SavedNote` = `filename` + `path` only) and
`dashboard/js/boot/notes.js` (the Notes UI is one flat, alphabetically-sorted list of
filenames — no folder, tag, or category field anywhere in the storage shape or the UI).
Adding a real category field would touch the storage model, both API routes, and the UI —
exactly the "new broad management-system build" the task said to avoid, and it could not be
tested or deployed from this sandbox anyway. The task's own specified fallback — ten
category-specific notes with clear titles — needs **zero code changes**, so that's what is
staged here.

## How to apply this (manual, on the live dashboard)

For each of the 10 sections below: Notes → **New note** → paste the **Title** into the name
box → paste the **Body** into the editor → Save. Order doesn't matter functionally, but
using the `01.`–`10.` numeric prefix shown keeps them grouped together in the flat list
instead of scattered among existing notes (which sort by save-date, newest first).

**Do not touch any existing note while doing this**, especially the deed note — this is
additive only, per the task's instruction to preserve all existing notes exactly and not
auto-reclassify them. If any existing note's category is unambiguous (e.g. the probate
STARTER note already bundled in `dashboard/js/boot/notes.js`'s "New note" default clearly
belongs under category 4), leave it where it is and reference it from that category note
rather than moving it — moves on flat-file storage are not reversible for free, and the task
says reclassification should wait.

---

## 01. Scoreboard Development

**Category 1 of 10 — staged 2026-11-05, not yet created live**

### WHY / SCOPE
Tennis scoreboard controller and the physical Kerun HUB75 64x64 LED panel display it drives:
scoring logic/state machine, display mapping and fonts, ghosting artifacts, layouts and score
states.

### KNOWN PROJECTS/EXAMPLES
- `src/skills/custom/running-tennis-scoreboard/SKILL.md` (this repo) documents
  `run_remote_listener`, its state machine (gameplay, pairing, sleep, undo, match-win), and
  runtime timing files (`game_blink_slowdown_delay_ms.txt`, `set_win_flash_delay_ms.txt`,
  `main_game_delay.txt`).
- Kerun HUB75 64x64 panel hardware, display mapping/fonts, and "ghosting" artifacts are
  referenced in the task framing but **not found anywhere in this repo** — last-known/
  unverified; likely lives outside `letta-code` or was described only verbally.

### OPEN ITEMS / VERIFY NEXT
- Confirm where the HUB75 panel driver/mapping code actually lives (separate repo? this
  host only?) — last-known/unverified.
- Inventory open bugs (ghosting, layout/score-state issues) directly with the user; none are
  recorded in this repo's skill doc beyond the state-machine description.

### KEY FILES/WORKSPACES
- `src/skills/custom/running-tennis-scoreboard/` (this repo) — build/run/debug guide only.
- Panel driver/mapping location: unknown, verify with user.

### LAST REVIEWED
2026-11-05 — all status above is last-known/unverified unless citing a specific file.

---

## 02. Finance & Bookkeeping

**Category 2 of 10 — staged 2026-11-05, not yet created live**

### WHY / SCOPE
River of Life ministry financial data: receipts, scanning, classification, bank statements,
expense tracking/reconciliation, plus Toyota/Mazda-related finance automation.

### KNOWN PROJECTS/EXAMPLES
- `dashboard/docs/finance-intake.md` (this repo) documents the ROL Finance reports, scanner
  health LEDs, scan → Mazda intake pipeline, Trainer escalation path, statement review flow,
  and LLM fallback chains.
- Mazda-named agents (`Mazda`, `Mazda Router`, `Mazda Parser`, `Mazda Vendor Identity`,
  `Mazda Receipt Linker`, `Mazda Categorization` — `dashboard/voice/config.py`) are the
  categorization/routing workers for this pipeline.
- `dashboard/trainer/reports/` holds dated Freezer/Window Scanner reports (e.g.
  `20260826-003049_Freezer_Scanner_*.md`) — last-known evidence the scanner pipeline has run;
  not verified as current/complete.

### OPEN ITEMS / VERIFY NEXT
- Current state of bank statement reconciliation — last-known/unverified, check
  `dashboard/docs/finance-intake.md` and the live Recent Report for the actual backlog.
- Any open Mazda escalations to Trainer — verify via the live dashboard, not assumed here.

### KEY FILES/WORKSPACES
- `dashboard/docs/finance-intake.md`, `dashboard/trainer/reports/`, Mazda agent family in
  `dashboard/voice/config.py`.

### LAST REVIEWED
2026-11-05 — status above is last-known/unverified unless citing a specific file.

---

## 03. Tax Preparation

**Category 3 of 10 — staged 2026-11-05, not yet created live**

### WHY / SCOPE
2024/2025 federal, Michigan, and Grand Rapids city tax preparation for Robert/Rosemary
Barnes; the GR city tax workflow and its supporting documentation.

### KNOWN PROJECTS/EXAMPLES
No references to this work (Robert/Rosemary Barnes, specific tax years, or a GR city tax
workflow) were found anywhere in this repo. This category exists per the task's explicit
instruction and should be treated as **entirely unverified from this codebase** — nothing
below should be read as confirming any filing has been started, estimated, or completed.

### OPEN ITEMS / VERIFY NEXT
- Confirm with the user whether any tax-year work has actually begun, and where its
  documents/workspace live (likely outside `letta-code` entirely, e.g. local files or a
  separate folder).
- When documentation exists, explicitly distinguish **estimates** from **verified/filed
  returns** in this note — do not conflate the two.

### KEY FILES/WORKSPACES
Unknown — not present in this repo. Verify with user.

### LAST REVIEWED
2026-11-05 — nothing in this category is verified; see note above.

---

## 04. Probate & Real Estate

**Category 4 of 10 — staged 2026-11-05, not yet created live**

### WHY / SCOPE
Father's estate probate: creditor resolutions, title and legal description review, deed of
distribution, property-tax exemption/uncapping review. **Never modify the deed note under
this or any task without the user present and explicit confirmation.**

### KNOWN PROJECTS/EXAMPLES
- The dashboard's own default "New note" starter text (`dashboard/js/boot/notes.js`, the
  `STARTER` constant) is itself a probate note: father listed as Louis Adams Sr., PR as
  Louis Herbert Adams Jr., "Court-certified Letters of Authority in force: November 3,
  2026," "Deed distribution: not yet prepared," with open items "Verify the legal
  description" and "Verify whether the estate actually closed." This is last-known/
  unverified content baked into the UI default, not confirmation that any of it is current.
- A separate, existing live note is referred to elsewhere as "Personal Representative's
  Deed" — **do not open, edit, or move it from this category note.** Link to it by its
  existing filename once confirmed live; do not reproduce or restate its contents here.

### OPEN ITEMS / VERIFY NEXT
- Verify the legal description (per the UI's own starter note).
- Verify whether the estate has actually closed.
- Property-tax exemption/uncapping review — status unknown, verify with user.
- Confirm the deed note's exact live filename and leave it exactly where it is.

### KEY FILES/WORKSPACES
- `dashboard/js/boot/notes.js` (`STARTER` text, for reference only — not a record of actual
  progress).
- Live deed note: filename unconfirmed from this sandbox; do not guess it.

### LAST REVIEWED
2026-11-05 — all task/status statements above are last-known/unverified.

---

## 05. AI Agents

**Category 5 of 10 — staged 2026-11-05, not yet created live**

### WHY / SCOPE
The worker fleet — Toyota, Mazda, Codex, Claude, and other specialist agents — their
architecture, coordination, and evaluation. Workers are distinct from shared infrastructure
(see category 06): Claude/Codex/Toyota/Mazda are **workers**; the Star Trek Bridge is the
**shared infrastructure** they run on top of.

### KNOWN PROJECTS/EXAMPLES
- Agent roster lives in `LETTA_AGENTS` (`dashboard/server.py`) and must stay in sync with
  `voice.config.KNOWN_AGENT_NAMES` (`dashboard/voice/config.py`): Scissari, Frita, Toyota,
  Shelia, Hailey, Jeri, Mazda (+ Router/Parser/Vendor Identity/Receipt Linker/
  Categorization), Suzuki (+ Router/Reproducer/Static Analysis/Patch/Test Runner/
  Regression).
- Toyota and Mazda's preferred "brain" is the `receptionist_team` sidecar
  (`~/agent_blocks/lancedb_memory`, outside this repo) rather than the Letta brain directly;
  a dead sidecar degrades to the Letta brain rather than breaking (`dashboard/docs/voice.md`).
- Sydney is Toyota's clone for non-financial work, same `SidecarBridge` pattern, no Letta
  fallback.

### OPEN ITEMS / VERIFY NEXT
- Any pending agent evaluations or responsibility changes — not recorded in this repo;
  verify directly.
- Confirm current health of each sidecar (`toyota-receptionist` :8767, `sydney-receptionist`
  :8769) via the live Server Management tab, not assumed here.

### KEY FILES/WORKSPACES
- `dashboard/server.py` (`LETTA_AGENTS`), `dashboard/voice/config.py`
  (`KNOWN_AGENT_NAMES`), `dashboard/docs/voice.md`.

### LAST REVIEWED
2026-11-05 — status above is last-known/unverified unless citing a specific file.

---

## 06. Star Trek Bridge & ADW

**Category 6 of 10 — staged 2026-11-05, not yet created live**

### WHY / SCOPE
Shared infrastructure (distinct from the workers it runs, see category 05): delegation,
workspaces, workflow phases, debugging visibility, agent task state, queue status,
pause/resume requests, machine hostname verification, Toyota Bridge connectivity.

### KNOWN PROJECTS/EXAMPLES
- The notes-bridge façade itself (`dashboard/notes_bridge.py`, `/api/notes-bridge/v1`) is
  part of this infrastructure: loopback-only, bearer-token auth, approved-notes allowlist,
  revision-checked writes, no create. Reached from ChatGPT via the Bridge worker's `notes`
  agent (`agent_blocks/lancedb_memory/agent_bridge_worker/notes_agent.py`, outside this
  repo), holding the `agent-bridge-notes` token.
- Every façade outcome and agent step logs to `NOTES_ACTIVITY_LOG`
  (`~/.cache/agent_bridge/notes_activity.jsonl`) and surfaces on **System Status > Worker
  Activity** via `agent_bridge_worker.activity_snapshot` — one row per Bridge task.
- `X-Bridge-Task: t_<hex>` is the mechanism by which a given task's events group together on
  that page — this is how task `t_ef0ad135cf930cae314baa7a` (the queued overview-note task)
  would show up there once it runs.

### OPEN ITEMS / VERIFY NEXT
- Current queue status / any paused tasks — check the live Worker Activity page, not this
  note.
- Machine hostname verification for the current live dashboard host — per
  `dashboard/CLAUDE.md` the live host is `DESKTOP-2OBSQMC`; confirm this is still current.

### KEY FILES/WORKSPACES
- `dashboard/notes_bridge.py`, `dashboard/docs/notes.md`, `dashboard/CLAUDE.md`
  ("Which machine is live" in `docs/operations.md`).

### LAST REVIEWED
2026-11-05 — status above is last-known/unverified unless citing a specific file.

---

## 07. Dashboards & Web Interfaces

**Category 7 of 10 — staged 2026-11-05, not yet created live**

### WHY / SCOPE
The dashboard frontend itself: five-row Worker Activity, blinking live worker status, the
existing Notes page, frontend components generally, previously-broken/repaired dashboard
issues, and the Notes read/edit/save diagnostic.

### KNOWN PROJECTS/EXAMPLES
- Recent fixes on `main` (per git log at the time of writing, last-known/unverified as to
  current state): receptionist alert cards using the alert's own title, Notes ignoring a
  duplicate Save while one is in flight, Notes surfacing why a save failed.
- `dashboard/js/boot/notes.js` is the whole Notes page controller: flat note list, open/
  save/refresh, autosave-on-idle, 5s polling with "edited elsewhere" conflict detection,
  Mermaid preview rendering.
- Frontend layering is documented in `dashboard/js/README.md`: `abstract/` = interfaces,
  `implementation/` = concrete DOM/fetch wiring, `boot/` = one module per section.

### OPEN ITEMS / VERIFY NEXT
- Whether the "Notes read/edit/save diagnostic" referenced in the task is a specific open
  bug or just the general diagnostic text already in `notes.js` (`notes-diagnostic` element)
  — unverified, ask the user which they meant.
- Current state of five-row Worker Activity / blinking live status — verify on the live
  page, not assumed here.

### KEY FILES/WORKSPACES
- `dashboard/js/boot/notes.js`, `dashboard/js/boot/worker-activity.js`,
  `dashboard/css/worker-activity.css`, `dashboard/docs/worker-activity.md`.

### LAST REVIEWED
2026-11-05 — status above is last-known/unverified unless citing a specific file.

---

## 08. Document Automation

**Category 8 of 10 — staged 2026-11-05, not yet created live**

### WHY / SCOPE
The scanner pipeline (Scala/window/freezer scanners), OCR/PDF/Word handling, editing,
formatting/colorization, and export/email preparation. **No email is ever sent without
explicit user approval** — this applies to this note's handling too; nothing here triggers
a send.

### KNOWN PROJECTS/EXAMPLES
- `dashboard/trainer/reports/` contains dated Window Scanner and Freezer Scanner reports
  (e.g. `20260730-174313_Window_Scanner_*.md`, `20260826-003049_Freezer_Scanner_*.md`) —
  last-known evidence the pipeline has run; not verified as to current accuracy.
- `dashboard/notes_docx_export.py` and `dashboard/notes_email_draft.py` exist in this repo
  — Word export and email-drafting code paths. **Not confirmed whether email-draft ever
  sends without a separate explicit approval step; verify before relying on this note's
  framing.**
- `dashboard/tests/test_document_annotation.py` references OCR annotation (`tesseract`),
  confirming an OCR/annotation path exists in code, not that it is complete or bug-free.

### OPEN ITEMS / VERIFY NEXT
- Confirm the actual send-approval gate in `notes_email_draft.py` matches the "no send
  without approval" rule before treating it as settled.
- Inventory current OCR/PDF/Word formatting issues directly — none recorded here.

### KEY FILES/WORKSPACES
- `dashboard/notes_docx_export.py`, `dashboard/notes_email_draft.py`,
  `dashboard/trainer/reports/`, `dashboard/tests/test_document_annotation.py`.

### LAST REVIEWED
2026-11-05 — status above is last-known/unverified unless citing a specific file.

---

## 09. Computer Systems & Networking

**Category 9 of 10 — staged 2026-11-05, not yet created live**

### WHY / SCOPE
Windows/WSL Linux desktops, hostnames, services, the Letta server, MCP endpoints,
credential safety, networking, and bridge host mapping.

### KNOWN PROJECTS/EXAMPLES
- Live dashboard host: `DESKTOP-2OBSQMC`, `Ubuntu-26.04` (codename `resolute`),
  Tailscale IP `100.102.209.100`, user `adamsl` (`dashboard/CLAUDE.md`) — last-known,
  reverify before relying on it for any SSH action.
- Letta API default `LETTA_BASE_URL=http://100.80.49.10:8283` (`dashboard/server.py`,
  `dashboard/voice/config.py`).
- `src/permissions/` (`~/.letta/settings.json` + `.letta/settings.local.json`) governs
  permission modes for the `letta` CLI itself.
- `src/utils/secrets.ts`, `src/utils/secretsStore.ts`, `src/utils/aws-credentials.ts`
  (this repo, currently modified per `git status` at session start) — credential-handling
  code; **do not assume the current working-tree state of these files is finished or
  reviewed** since they show as locally modified.
- Canonical machine list: the `sync-all` skill (per `dashboard/CLAUDE.md`, "trust it over
  this file").

### OPEN ITEMS / VERIFY NEXT
- Confirm current credential-handling changes in `src/utils/secrets*.ts` are intentional
  and reviewed, not stray WIP from a concurrent agent — `git status` showed them modified.
- Reverify the live host/IP pairing before any SSH or deploy action; it is explicitly
  documented as something that can drift (`dashboard/CLAUDE.md`).

### KEY FILES/WORKSPACES
- `dashboard/CLAUDE.md` ("Deploying" section), `dashboard/server.py`,
  `dashboard/voice/config.py`, `src/permissions/`.

### LAST REVIEWED
2026-11-05 — status above is last-known/unverified unless citing a specific file.

---

## 10. Other Engineering Projects

**Category 10 of 10 — staged 2026-11-05, not yet created live**

### WHY / SCOPE
Miscellaneous prototypes and side projects: sprinkler automation, vehicle diagnostics,
Raspberry Pi experiments, VR photo viewing, and anything else that doesn't fit the other
nine categories.

### KNOWN PROJECTS/EXAMPLES
A repo-wide search for "sprinkler", "Raspberry Pi", and "VR photo" found **no matches
anywhere in `letta-code`**. Per the task's own instruction to verify before making specific
claims here: none of these four projects have any confirmed presence in this codebase.
Treat all four as last-known/unverified, external to this repo, or not yet started — do not
state otherwise without checking with the user directly.

### OPEN ITEMS / VERIFY NEXT
- Confirm with the user which of sprinkler automation / vehicle diagnostics / Raspberry Pi
  experiments / VR photo viewing are actually active, and where (if anywhere) their
  workspace lives.

### KEY FILES/WORKSPACES
None found in this repo. Verify with user.

### LAST REVIEWED
2026-11-05 — nothing in this category is verified; see note above.

---

## Overview / Navigator note (draft — check for the queued task's note first)

**Only create this if the live Notes list does not already contain**
*"Project Organization Brainstorm — Department / Project / Task (2026-11-05)"* **from task
`t_ef0ad135cf930cae314baa7a`.** If it exists, merge the points below into it instead.

> # Notes Organization Overview (2026-11-05)
>
> This dashboard's Notes tab now has 10 category starter notes (`01.` through `10.`,
> titles below) alongside all previously existing notes, which were left untouched.
>
> **Categories:** 01 Scoreboard Development · 02 Finance & Bookkeeping · 03 Tax Preparation ·
> 04 Probate & Real Estate · 05 AI Agents · 06 Star Trek Bridge & ADW · 07 Dashboards & Web
> Interfaces · 08 Document Automation · 09 Computer Systems & Networking · 10 Other
> Engineering Projects.
>
> **Suggested task schema going forward:** `Department > Project > Task`, each task carrying
> an assigned agent, status, priority, source, artifacts, and next action. This is a
> convention for how notes/tasks are *written*, not a new storage system — the Notes tab
> remains flat Markdown files; nothing new was built to enforce this schema.
>
> **Keep distinct:** Claude, Codex, Toyota, Mazda, and the other named agents are **workers**;
> the Star Trek Bridge is **shared infrastructure** they run on, not a project or a worker
> itself.
>
> **Durable per-project notes/decisions/history:** use the matching category note above as
> the landing point for a project's ongoing notes; create a new dated note under that
> category for a specific decision or incident rather than editing the category note's
> history away.
>
> **Recommended next action:** before building any broader tooling on top of this, spend
> time inventorying roughly the last 3 months of repos/tasks/notes so the category notes
> above are filled in with confirmed (not last-known/unverified) status. None of the status
> claims in the 10 category notes should be treated as settled until that inventory happens.

---

## Summary for the task requester

| # | Category | Live note created? | Note ID |
|---|---|---|---|
| 1 | Scoreboard Development | No | — |
| 2 | Finance & Bookkeeping | No | — |
| 3 | Tax Preparation | No | — |
| 4 | Probate & Real Estate | No | — |
| 5 | AI Agents | No | — |
| 6 | Star Trek Bridge & ADW | No | — |
| 7 | Dashboards & Web Interfaces | No | — |
| 8 | Document Automation | No | — |
| 9 | Computer Systems & Networking | No | — |
| 10 | Other Engineering Projects | No | — |
| — | Overview/navigator note | No (check for `t_ef0ad135cf930cae314baa7a`'s note first) | — |

**Read-back/live persistence evidence:** none — nothing was written live, so there is
nothing to read back yet. This file is the complete staged content; applying it live is a
manual step (see "How to apply this" above) or a follow-up task with actual access to the
live host and/or an approved path through the notes-bridge.

**Code changes:** none. **Tests:** none run (no command execution available in this
sandbox; also no code was changed, so none were needed). **Deploy/commit/push/email:**
none, as instructed. **Deed note:** not opened, not touched.
