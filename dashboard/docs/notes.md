# Dashboard Notes

The Notes tab stores Markdown files in `NOTES_DIR` (default: `~/notes`). The
browser uses `/api/notes` to list/read and `/api/note-save` or
`/api/note-write` to create/update notes. Open the dashboard, choose **NOTES**,
select **New note**, enter a name and text, and choose **Save Note**. Existing
notes can be reopened from the list and edited.

Storage itself stays flat — one `.md` file per note, no category field
anywhere in `SavedNote` or the API. The browser list (`js/boot/notes.js`)
groups that flat list into 10 standing category accordions (plus "All other
notes" for anything that doesn't match) purely for display: it reads a
leading `NN-` token off the saved filename's slug (so naming a note
`01. Scoreboard Development` saves as `<date>_01-scoreboard-development.md`
and groups under category 01) and never reclassifies a note by guessing at
its content. All 10 category headers render every time, even before a note
exists in them — a category with no notes yet shows "No notes in this
category yet." in its body rather than disappearing, so there is always
something to open (and a name to copy into the editor's name box). "All
other notes" is the exception: it only appears once a note without a
category token exists. Each category is a plain `<details>`/`<summary>` —
the same disclosure widget already used for `.mtr-detail` on the System
Status "Mazda tool reconciliation" panel — so categories expand and collapse
independently with native keyboard support, and nothing new was added to the
storage layer or the save/open/poll/autosave flow. The 10 categories, in
order: Scoreboard Development, Finance & Bookkeeping, Tax Preparation,
Probate & Real Estate, AI Agents, Star Trek Bridge & ADW, Dashboards & Web
Interfaces, Document Automation, Computer Systems & Networking, Other
Engineering Projects.

## Formatting

A note is Markdown (headings, `-`/`*` bullets, `**bold**`, `` `code` ``) plus
one more inline span, `{{color:name}}text{{/color}}` or
`{{highlight:name}}text{{/highlight}}` (`name` from the fixed palette in
`notes_formatting.COLORS` — e.g. `{{highlight:yellow}}`). That module is the
one place the markup is defined; the browser preview (`js/boot/notes.js`
`markdownHtml`), the Word export and the email draft each render it their own
way, but all three treat an unknown color name or an unclosed span as the
literal text, never raising or inventing markup the note's own text didn't
supply. In the browser, a highlight renders as a `<mark>` with a pastel
background and a color span as colored text (`.notes-highlight-*`/
`.notes-color-*` in `css/dashboard.css`).

## Agent integration point

The secured façade is `/api/notes-bridge/v1` (`notes_bridge.py`). It uses the
existing scan-bridge client file and bearer-token mechanism
(`scan_jobs/auth.py`): loopback callers only, no browser requests, a token
whose SHA-256 is in `SCAN_BRIDGE_CONFIG_DIR/clients.json`, and scope
`notes:read` (GET) or `notes:write` (POST). On top of that:

- **Which notes.** With `{"all": true}` in `NOTES_BRIDGE_APPROVED`
  (`~/.config/startrek_notes/approved.json`) every note is reachable by an authorized client, so no filename
  needs approving one by one; that is how ChatGPT and Toyota run on the live box. Without it the file is the
  per-filename list `{"notes": ["<filename>", ...]}` and only those names are reachable; a missing or
  unreadable file approves nothing. `all` must be the JSON `true` -- any other value is not "all".
- **Protected notes** (`NOTES_BRIDGE_PROTECTED`, default `~/.config/startrek_notes/protected.json`) stay
  readable but every write, rename or trash of them is refused, in either mode. This is the lock for a note
  (the deed) whose corrections must be authorized some other way.
- **Create is allowed, overwrite is not.** `POST /notes` makes a new dated file and never replaces one; a name
  clash gets `-2`, `-3`. Nothing here deletes bytes except `purge`, below.
- **No blind overwrite.** Every write carries the revision a read returned
  (the sha256 of the file bytes, the same value `/api/notes` gives the
  browser). A missing revision is a 428, a stale one a 409 with the current
  revision, and nothing is written.

Calls:

- `GET /api/notes-bridge/v1/notes` — notes the Bridge may reach. `?q=text` searches names and bodies (matching lines
  returned), `?category=N` filters (1-10, the `NN-` token of the filename); either adds `entries` with revisions.
- `POST /api/notes-bridge/v1/notes` with `{"name", "note", "category"?}` — create (`notes_library.py`); `{filename, revision}`
- `POST .../notes/<filename>/rename` with `{"expected_revision", "new_name"?, "category"?}` — rename and/or move to a
  category (`0` = no category). The date prefix and the text are untouched; an existing name is refused.
- `POST .../notes/<filename>/trash` with `{"expected_revision"}` — move to `NOTES_DIR/.trash/` (a dot-directory the
  browser list never shows); returns `trash_id`. Recoverable.
- `GET .../trash` — what is in the trash. `POST .../trash/<trash_id>/restore` — put it back (never over a reused name:
  it becomes `...-restored.md`).
- `POST .../trash/<trash_id>/purge` with `{"authorization": "EG authorizes permanently deleting <trash_id>"}` — the
  only call that removes bytes. Only from the trash, only with that exact sentence (`notes_library.purge_phrase`);
  anything else is a 403 and nothing is deleted.
- `GET /api/notes-bridge/v1/notes/<filename>` — `{note, revision}`
- `POST /api/notes-bridge/v1/notes/<filename>` with
  `{"filename", "note", "expected_revision"}` — `{revision}` of the saved file
- `GET /api/notes-bridge/v1/notes/<filename>/highlights` — `{filename, revision, highlights, review_marks}`:
  every persisted `{{highlight:name}}` span, plus (for the Personal Representative's Deed only) the page's yellow
  review marks, computed by `notes_review_marks.py` -- a port of `deedReviewKind` that `tests/test_notes_review_marks.py`
  runs against the browser's own rule so the two cannot drift. A review mark is cleared by resolving its text
  (an ordinary edit); the page drops it on its next 3 s poll.

### "What is highlighted in this note?" — three different things named "highlight"

This note format has three things that can look like "a highlight" to a reader, and they are not
interchangeable:

1. **A persisted highlight span.** `{{highlight:name}}text{{/highlight}}` written into the note's
   own saved Markdown (see "Formatting" above). This is the only kind `/highlights` reports. It is
   not a separate offset stored anywhere — it travels inline with the text itself, so reading the
   note and looking for these spans *is* reconstructing it, correctly, every time, with no drift
   possible between save and reopen.
2. **The Personal Representative's Deed page's view-only review marks** (reported separately, as `review_marks`)
   (`js/boot/notes.js` `deedReviewKind`/`isPersonalRepresentativeDeed`). For that one note only, the
   browser renders certain sentences (a preparer line, a legal description, tax language) as
   `<mark>` purely by pattern-matching the saved text at render time — nothing is written to the
   file for this, so there is no span to report here. `highlights` excludes these; `review_marks` reports them.
3. **An unsaved browser text selection.** Selecting text in the editor's textarea is pure browser
   state; it is never sent to the server and never becomes part of the saved note. There is
   therefore no code path by which it could be confused with (1) — the façade only ever reads bytes
   already on disk.

When EG asks "what is highlighted in the Personal Representative's Deed notes," the answer is (1):
call `GET /api/notes-bridge/v1/notes/<deed filename>/highlights` (or
`notes_bridge_client.NotesBridgeClient.highlights(filename)`, or
`python3 scripts/chatgpt_notes_cli.py highlights <deed filename>`) and read back each item's
`"text"` field. Each item is:

```json
{"text": "verify the legal description", "color": "yellow", "line": 7,
 "start": 142, "end": 171, "context_before": "Please ", "context_after": " before filing."}
```

`text` is the exact substring between the span tags — byte-for-byte, not paraphrased. `color` is one
of `notes_formatting.COLORS` (`yellow`, `red`, …). `line` is the 1-based line number in the saved
file; `start`/`end` are character offsets of `text` within that same saved file, recomputed from the
current bytes on every call (`notes_highlights.py`) rather than stored, so they can never go stale.
`context_before`/`context_after` are up to 40 characters of markup-stripped text from the same line,
for a human- or TTS-readable anchor ("the sentence right before/after this highlight"). The note's
own `filename` plus the `revision` returned alongside `highlights` together form a stable identity
for "this exact highlighted version of this note" — if `revision` differs from a prior read, the
underlying text (and therefore any highlight) may have changed.

### Verifying this against the live note, not a cached answer

Because `/highlights` recomputes its answer from `repository.read(filename)` on every call, there is
nothing to "go stale" the way a cached index could — but a caller that wants to double-check should:

1. Call `/highlights` and note its `revision`.
2. Call `GET /api/notes-bridge/v1/notes/<filename>` (plain read) and confirm it returns the *same*
   `revision`, and that every `highlights[i].text` actually appears as
   `{{highlight:highlights[i].color}}...{{/highlight}}` in that `note` body.
3. Separately, the browser's own `/api/notes` (what the Notes page itself polls) should report the
   same `revision` for the same filename — if it doesn't, something wrote to the note between steps,
   and the highlights just read are for an earlier version of the text.

No claim is made here that a live ChatGPT Bridge task has actually exercised this end to end — see
"Blocker" below.

A caller may send `X-Bridge-Task: t_<hex>` so its events group under its
Bridge task on the Worker Activity page.

### From ChatGPT and Toyota: the Star Trek Bridge `notes` agent

ChatGPT reaches this through the Bridge worker's `notes` agent
(`agent_blocks/lancedb_memory/agent_bridge_worker/notes_agent.py`), which
holds the `agent-bridge-notes` token. The task prompt is JSON:

```json
{"notes": "list"}                                                    // inspect
{"notes": "read", "id": "<filename>"}                                // inspect: body is {id, revision, note}
{"notes": "update", "id": "<filename>", "expected_revision": "<from read>",
 "edits": [{"find": "<exact text>", "replace": "<new text>"}]}       // implement
```

The full set (both agents have all of it; `notes_ops/commands.py` in `agent_bridge_worker` has one Command per row,
`receptionist_team/bridge_client/notes_plans.py` the matching Plan for Toyota):

| operation | lane | takes |
|---|---|---|
| `list` / `search` | inspect | optional `query`, `category` (search needs `query`) |
| `read` | inspect | `id` |
| `highlights` | inspect | `id` -- saved spans and the deed's review marks |
| `refresh` | inspect | `id`, `known_revision` -- changed? returns the new text only if so |
| `trash_list` | inspect | |
| `update` | implement | `id`, `expected_revision`, `edits` (each ONE of `find` / `line` / `section` / `append`, + `replace`) or `text` |
| `highlight` | implement | `id`, `expected_revision`, `marks`: `{action: add\|recolor\|clear, text, color}` or `{action: clear, all: true}` |
| `create` | implement | `name`, `text`, optional `category` |
| `rename` | implement | `id`, `expected_revision`, `new_name` and/or `category` (0 = none) |
| `trash` / `restore` / `purge` | implement | `id`+`expected_revision` / `trash_id` / `trash_id`+`authorization` |

Every change reads back through the interface and the dashboard's own endpoint before it reports success
(`highlight` also checks the dashboard's `/highlights` agrees, so a colour the page cannot render is not "done").
A task prompt is capped at 8000 characters by the gateway, so a long document is a `create` followed by `append` edits.

`text` (the whole note) may replace `edits`. Each `find` must occur exactly
once in the note as it stands, or nothing is written; text outside the edits
is carried over byte for byte. After the write the agent reads the note back
through this façade *and* through the browser's own `GET /api/notes`, and
succeeds only if both return the expected text at the revision the write
reported. The task's summary and details carry `revision_before`,
`revision_after` and `verified`; its body carries a unified diff.

The browser's Notes page polls `/api/notes` every 3 s (`js/boot/notes.js`
`pollSelected`) and picks up the new revision on its own, without
overwriting unsaved edits; **Refresh Notes** reloads it on demand. A patch
applied this way only swaps `textarea.value` and rebuilds the preview pane's
`innerHTML` — not the surrounding page — and restores the textarea's caret
and both panes' scroll position afterward, so an open note updates in place
without a manual reload, a lost reading position, or a lost in-progress
caret. `{{highlight:name}}`/`{{color:name}}` spans (see "Formatting" below)
render immediately as part of that same patch — a yellow highlight a Bridge
task just wrote, for instance, appears in the open preview on the next poll,
no refresh needed.

### Activity log

Every façade outcome (`list`, `read`, `write`, `conflict`, `refused`,
`not_approved`, `auth_failed`, `error`, `export_docx`, `email_draft`,
`highlights`) and every agent step (`verified`,
`verify_failed`, `conflict`, `refused`, `auth_failed`, `unchanged`) is one
JSON line in `NOTES_ACTIVITY_LOG` (default
`~/.cache/agent_bridge/notes_activity.jsonl`, mode 0600): event, filename,
revisions, client name, Bridge task id, short reason — never note text.
`agent_bridge_worker.activity_snapshot` turns it into `notes` rows on
**System Status > Worker Activity** (one row per Bridge task; an event
without a task id is a row of its own).

### Provisioning (once per host)

```bash
python3 scripts/provision_notes_bridge_client.py --name agent-bridge-notes \
    --token-file ~/.config/startrek_notes/notes_token
```

merges an `agent-bridge-notes` client (`notes:read`, `notes:write`) into
`clients.json` without touching any other client, and writes the plaintext
token to a 0600 file in a 0700 directory instead of printing it. The worker
reads it from there at start (`load_scan_token` refuses a file anyone else
can read); restart `agent-bridge-worker` afterwards. `--rotate` replaces the
token. Without `--token-file` the script prints the token once, for the
scripting client below.

### Script client: `notes_bridge_client.py` and `scripts/chatgpt_notes_cli.py`

`NotesBridgeClient` (`read`, `write`, `write_and_verify`, `remove_text`,
`remove_text_and_verify`, `export_docx`, `email_draft`, `highlights`) and the
CLI over it speak the same façade for scripts on this host, with a token from
`NOTES_BRIDGE_TOKEN`. They follow the same rules — approved notes only, a
revision on every write, no create (`create` is refused with a 403).

```bash
python3 scripts/chatgpt_notes_cli.py list
python3 scripts/chatgpt_notes_cli.py read deed.md
python3 scripts/chatgpt_notes_cli.py highlights deed.md
echo "updated text" | python3 scripts/chatgpt_notes_cli.py update deed.md --expected-revision <revision>
printf '%s' '[placeholder] ' | python3 scripts/chatgpt_notes_cli.py remove-text deed.md --expected-revision <revision>
```

### Blocker: wiring this into a live Star Trek Bridge "notes" tool call is out of this checkout

Everything above (`notes_bridge.py`'s `/highlights` route, `notes_highlights.py`,
`NotesBridgeClient.highlights`, the CLI's `highlights` subcommand, and their tests) is implemented
and testable here. What is **not** present in this writable checkout, and was not touched or
claimed as working:

- The Bridge worker's own `notes` agent (`agent_blocks/lancedb_memory/agent_bridge_worker/notes_agent.py`
  per this doc's existing text above) lives in a different repository on the host
  (`~/agent_blocks/lancedb_memory`), not under `letta-code/`. Teaching that agent a new
  `{"notes": "highlights", "id": "<filename>"}` task shape — so a ChatGPT turn can actually reach
  this new endpoint — is a change in that other repository, not this one.
- `NOTES_BRIDGE_APPROVED` (`~/.config/startrek_notes/approved.json`) is host configuration, not
  code; whether the Personal Representative's Deed note's real filename is on that list is an
  operator decision outside this checkout and was not changed here.
- No live round trip (ChatGPT → Bridge worker → this façade → the real deed note) was run as part of
  this change — only the automated tests above, against fixture notes and a throwaway
  `NOTES_DIR`/`clients.json`, which never touch the real `~/notes` directory or any real note
  content.
