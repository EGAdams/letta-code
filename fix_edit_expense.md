# FIX NEEDED: the Edit Expense button can never be used

**Status: FIXED and live, 2026-08-19, commit `6b7e773a`.** The recommended fix
below is what was built. Verified on the serving box:
`/scanner_report.html?scanner=freezer` (status `complete`) now carries
`expense-edit-root`, and the `window` page still shows exactly one Edit Expense
button. All three machines are on `origin/main` at `6b7e773a`.

The only open item left in this file is the last section — the 13 failing
scanner-intake tests, still failing, still uninvestigated. They are unrelated
to this fix (confirmed by `git stash`: identical 17 failures with and without
the change).

Written 2026-08-19. Everything below was verified against the running
dashboard, not guessed.

---

## What EG saw

He opened the Last Freezer Scan page and his edit buttons were gone.

## What is actually wrong

The **Edit Expense** button only appears while a scan is still waiting to be
typed in by hand. The moment you press **Save All**, the whole form vanishes —
and it takes Edit Expense with it.

But Edit Expense exists *specifically* to correct a row you already saved.
Wrong merchant, wrong date, wrong amount. So it disappears at exactly the
moment it becomes useful. **Right now there is no way to reach it at all.**

This is not a CSS problem and not the win98 restyle. The button is never put
on the page in the first place.

## Proof

Two scanner pages, fetched live on 2026-08-19:

| Page | Its status | Form on the page? |
|---|---|---|
| `/scanner_report.html?scanner=window` | `needs_human_review` | yes |
| `/scanner_report.html?scanner=freezer` | `complete` | **no** |

The freezer scan reads:

```
status: complete
status_detail: "Entered manually by operator — expense_id=2189"
```

Someone already saved it by hand. That is why the buttons went away.

## The one line responsible

`dashboard/server.py:1778`

```python
manual_entry_html = (
    intake_report_page.manual_entry_form_html(
        intake.get('image_path'), intake.get('conversation_id'), scanner_key)
    if intake_status == 'needs_human_review' else '')
```

If the status is anything other than `needs_human_review`, the page gets an
empty string, and every button in the form is gone: Edit Expense, Save All,
Prefill from OCR, Fill with Gemini, Fill with Haiku, Show Image, Prev/Next,
Break Up Document.

## The good news — this is cheaper than it looks

Two things make it easy, both confirmed:

**1. The server side already works everywhere.** `/api/expense-search` and
`/api/expense-edit` (`server.py:11576` and `:11583`) have no status check on
them at all. They will answer right now, on any scan. Only the browser-side
button is missing.

**2. The dialog is already a separate, self-contained piece.**
`js/implementation/expense-edit-dialog.js` (377 lines) takes only injected
options and does not reach into the entry form:

```js
new ExpenseEditDialog({ http, root, doc, categoryNames, onSaved, onSelected })
```

It is currently built at `js/implementation/manual-entry-form.js:464`, but
nothing about it requires that parent. It was deliberately written as its own
part — see the note in commit `9bf4d7f4`.

## Recommended fix

**Give Edit Expense its own mount point, shown on every scan page. Leave Save
All exactly where it is.**

Do NOT just delete the status check and show the whole form always. Save All
only ever *inserts* new rows. Putting it back on a page whose scan is already
saved invites entering the same receipt twice. Keeping the two halves separate
is the whole point.

Suggested steps:

1. In `finance/intake_report_page.py` (beside `manual_entry_form_html`, line
   102), add a small function emitting an edit-only mount point — a `<div>`
   plus the `<script type="module">` line. Same shape as the existing one.
2. In `server.py`, render that one unconditionally, right where line 1778
   decides about the form.
3. Add a small browser entry file that builds `ExpenseEditDialog` on its own.
   It needs `categoryNames`, which comes from `GET /api/rol-finance-categories`
   — see `_loadDropdownOptions` at `manual-entry-form.js:539` for the pattern,
   including its "a failed fetch just leaves the operator typing by hand"
   fallback.
4. Leave `manual-entry-form.js` alone apart from not double-mounting the dialog
   when the full form *is* on the page. Guard against two copies appearing.

Tests to extend: `dashboard/tests/test_intake_report_page.py`,
`dashboard/js/tests/` (the dialog already has coverage under
`js/abstract/expense-edit.interface.js`).

## Before you start — read this

- **The live dashboard is on DESKTOP-2OBSQMC, `adamsl@100.102.209.100`.** It is
  almost certainly not the machine you are typing on. Editing your own checkout
  changes nothing that EG can see.
- **Run the `sync-all` skill first** (`.claude/skills/sync-all/SKILL.md`). All
  three machines were brought onto `origin/main` at `6d6523e1` on 2026-08-19,
  after a bad split where the same feature got written twice on two boxes.
  Keep it that way. **Never branch — everything goes on `origin/main`.**
- After changing `server.py`:
  `systemctl --user restart dashboard-server.service`, then confirm with
  `dashboard/verify-live.sh "<something from your change>"`.

## Unrelated, but somebody should look

`dashboard/tests/test_server.py` has **13 failing tests**, all scanner intake
ones. They were already failing before the 2026-08-19 merge — that merge did
not cause them, and did not fix them. Nobody has investigated.
