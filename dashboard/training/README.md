# ROL Finance Training tab

Open Dashboard → ROL Finance → Training, immediately after Edit Expense.
The manual is also directly available at `/training/index.html`; append
`#first-session` to bookmark the practice lesson.

The existing finance navigation binds the new markup tab automatically. No
backend route, receptionist prompt, finance save behavior, or dashboard service
restart is required. Reload the dashboard after deployment to see the tab.

## Edit the lessons

- `src/content.ts`: the chapter catalog and current capability descriptions.
- `src/practice.ts`: the synthetic expense walkthrough.
- `src/architecture.ts`: Web Component and GoF lessons.
- `src/main.ts`: composition root that injects adapters through typed interfaces.
- `src/watch-a-run.ts`: the second practice lesson and evidence viewer block.
- `src/evidence/`: runtime decoding, read-only HTTP Adapter and injected renderer.
- `../../../the-factory/src/components/`: the nine shared custom elements.

Add a chapter to the catalog; its TOC entry, search text, and Previous/Next
position are derived automatically. Keep chapter and step IDs stable. Use the
`placeholder` block kind and literal `{to_be_implemented}` for unfinished work.
The manual does not send requests to Toyota or save expenses. Copy buttons only
copy examples; personal checkmarks are stored separately in localStorage.

## Second lesson: watch a run

Open `/training/index.html#watch-a-run`, or choose **Your second practice
session** in Contents. **Refresh evidence** reads the existing
`GET /api/receptionist-work` and `GET /api/receptionist-work/trace?run=...`.
It never claims browser work, posts instructions, starts an ADW or edits expenses.
The current checkpoint and selected historical run are labeled separately.
The checkpoint category is not a fresh database read or save confirmation.

`IWorkflowInspector` is the component's interface; `InspectionSession` receives
`IWorkflowEvidenceSource`. `ReceptionistEvidenceSource` implements that port
using the existing routes, and validates unknown JSON before presentation.
`WorkflowEvidenceRenderer` is registered through the default block factory's
extension map. It also supplies the app-specific recorded-events link through
the inspector's `run-link` slot. The library has no endpoint URLs.

Reads are manual, have a 15-second timeout, and cancel on component removal.
Superseded responses cannot replace newer evidence. A failed refresh hides
previous evidence, reports the failure, and permits another read. The trace
endpoint returns at most 500 events; the viewer marks this possible truncation
and never treats a missing phase ending as proof of running or success.
Reading-checkpoint version stays at 1, preserving the first lesson's progress.

```bash
bun install --frozen-lockfile
bun run test
bun run typecheck
bun run build
bun run test:browser
```

Build output `dist/manual.js` is the deployable asset, generated from TypeScript
and the shared library's HTML/CSS templates. Rebuild after changes to either
lessons or components. Keep it with the HTML when deploying. Sibling checkouts
of `letta-code` and `the-factory` are used for source imports. `bun.lock` pins
the isolated build/test tools; no root application dependency was changed.

Browser coverage checks real rendering and navigation, keyboard activation,
bookmarks/history, search, persisted/reset checkmarks, clipboard success and
failure, blocked storage, literal attribute text, component reconnection, phone
width, absence of financial POST requests, and the actual dashboard tab.

Second-lesson verification (2026-10-18): 27 unit/content tests, strict browser
and tooling TypeScript checks, and 10 browser scenarios passed. The existing
navigation screenshot and dashboard scenario needed a rerun after Chrome
capture/timeout failures. Live read-only decoding confirmed expense #900001
and run `acc6914c` with its three completed phases; no expense was changed.
An additional live viewer screenshot timed out in Chrome after the checkpoint
and phase elements rendered. Screenshot capture remains unreliable on this
host; the browser behavior assertions and live endpoint checks passed.
