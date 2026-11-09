# Notes: what ChatGPT and Toyota can do through the Bridge

Both agents reach every note on the Notes page through the same dashboard interface
(`/api/notes-bridge/v1`, `notes_bridge.py`). ChatGPT sends the JSON task below to the Bridge `notes` agent
(`agent_blocks/lancedb_memory/agent_bridge_worker`); Toyota fills the same operations from a spoken request
(`receptionist_team/bridge_client/notes_plans.py`) and reads each change back for a "yes" before sending it.

**Which notes.** `{"all": true}` in `~/.config/startrek_notes/approved.json` makes every note reachable by an
authorized client, so no filename needs approving one by one. Without it only the listed filenames are reachable.
`protected.json` still locks individual notes (writes, renames and deletes refused) in either mode.

| operation | lane | takes | route |
|---|---|---|---|
| `list` / `search` | inspect | optional `query`, `category` (1-10) | `GET /notes[?q=&category=]` |
| `read` | inspect | `id` | `GET /notes/<f>` |
| `highlights` | inspect | `id` -- saved `{{highlight}}` spans, the deed's static review marks, *and* its one active/blinking warning line (if any) | `GET /notes/<f>/highlights` |
| `refresh` | inspect | `id`, `known_revision` -- has it changed elsewhere? returns the new text only if so | `GET /notes/<f>` |
| `trash_list` | inspect | | `GET /trash` |
| `update` | implement | `id`, `expected_revision`, `edits` (each ONE of `find` / `line` / `section` / `append`, + `replace`) or `text` | `POST /notes/<f>` |
| `highlight` | implement | `id`, `expected_revision`, `marks`: `{action: add\|recolor\|clear, text, color}` or `{action: clear, all: true}` | `POST /notes/<f>` |
| `create` | implement | `name`, `text`, optional `category` | `POST /notes` |
| `rename` | implement | `id`, `expected_revision`, `new_name` and/or `category` (0 = none) | `POST /notes/<f>/rename` |
| `trash` | implement | `id`, `expected_revision` (recoverable) | `POST /notes/<f>/delete` |
| `restore` | implement | `trash_id` | `POST /trash/<name>/restore` |
| `purge` | implement | `trash_id`, `authorization` | `POST /trash/<name>/purge` |

* **A category is a file name.** Storage is flat; a category is the slug's leading `NN-` token
  (`2026-11-05_04-deed.md` is category 04). Moving a note to another category is a rename, computed by
  `agent_bridge_worker/notes_ops/names.py`. The text is never touched.
* **Purge is permanent and doubly guarded.** The dashboard accepts it only for a file already in `.trash/` and only when
  the body carries the exact sentence `EG authorizes permanently deleting <trash_id>`
  (`notes_bridge_extras.purge_phrase`). Toyota writes that sentence only after EG says "yes" to a read-back that says the
  delete cannot be undone. For ChatGPT, the sentence in the task is the record of EG's authorization.
* **Review marks.** The deed page paints yellow marks on lines that still hold a `[bracket]`, `NOT VERIFIED` or `VERIFY`.
  Nothing is saved for them, so `highlights` reports them separately as `review_marks` (line, kind, text, reason),
  computed by `notes_review_marks.py`, a port of the browser rule that `tests/test_notes_review_marks.py` runs against
  the browser's own code so the two cannot drift. Clearing one is an ordinary edit that resolves its text; the page drops
  the mark on its next 3 s poll, no reload.
* **The one active (blinking) line is not a review mark.** Exactly one kind of line gets a *blinking*
  background instead of a static mark: a bracketed "...VERIFY WITH ... ATTORNEY/PROBATE COURT..." sentence, but only
  inside the "Authority of the Personal Representative" section (`.notes-deed-review-active-line` in
  `css/dashboard.css` / `js/boot/notes.js` `isActiveAttorneyWarning`). `highlights` reports it as `active_warning`:
  `{"line", "text"}`, or `null` when the note currently has none -- computed by `notes_active_warning.py`
  (`tests/test_notes_active_warning.py` cross-checks it against the browser's code the same way). It is never also
  counted in `review_marks`: the browser renders a line as either the active span or a static mark, never both, so the
  façade drops that line from `review_marks` to match. Ten possible static categories and one possible active line are
  different questions -- the count of `review_marks` is never an answer to "what is blinking right now."
* **Every change is verified.** After a write the agent reads the note back through the interface and through the
  dashboard's own `GET /api/notes`; `highlight` also checks that `/highlights` reports the spans. It succeeds only if all
  agree. A stale `expected_revision` is a conflict and nothing is written.
* **Size.** A task prompt is capped at 8000 characters by the gateway; a long document is a `create` followed by
  `append` edits.
* **Watching it live.** `adws/adw_notes_highlight_watch.py` opens the Notes page in headless Chrome
  (selenium-headless `WebBrowserManager(headless=True)`) and, with `--until-clear TEXT`, waits without reloading for
  the page's own poll to drop the highlight on that text.
When a single persisted passage must blink, include exactly one standalone
HTML comment marker: `<!-- notes-review-focus: exact paragraph text -->`. The
text must match one rendered paragraph exactly; the marker is metadata and is
not part of the note's visible content or review marks. A missing or repeated
target intentionally produces no active pulse, so remove or correct the marker
before retrying. Without a valid marker, the legacy Authority-section warning
rule is used.
