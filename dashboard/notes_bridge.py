"""Token-protected agent facade for the dashboard's filesystem notes. Full
contract and rationale: ``docs/notes.md``.

This is the HTTP contract the Star Trek Bridge worker's ``notes`` agent calls
(``agent_blocks/lancedb_memory/agent_bridge_worker/adapters/notes_bridge_http.py``);
``notes_bridge_client.py`` is the same contract for scripts. Browser routes
stay separate so their behaviour is unchanged.

This module is only the router: match a route, authenticate
(``scan_jobs/auth.py``, ``notes:read``/``notes:write``), resolve scope
(``approved_notes`` -- ``None`` for "every note the repository exposes",
a ``frozenset`` for the legacy per-filename allowlist, see ``in_scope``)
and protection (``protected_notes`` -- read-only regardless of scope), call
the one matching handler, log its outcome via ``notes_activity`` (names and
revisions only, never note text), return. ``notes_bridge_core.py``
(list/read/write) and ``notes_bridge_notes.py``
(create/rename/delete/restore/list-trash) hold the operations themselves,
both returning the same ``(status, payload, event, log_fields)`` shape so
this module has one logging call site regardless of which operation ran.
Every write, rename, or delete carries the revision a prior read returned;
a stale one is a 409 and nothing changes -- ``create`` has nothing to
collide with, and ``delete`` is soft (moves the note to ``.trash/``, see
``voice/note_repository.py``), so ``restore`` can always bring it back.

A caller may send ``X-Bridge-Task: t_<hex>`` so its events group under its
Bridge task on the Worker Activity page.
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import notes_activity
import notes_bridge_core
import notes_bridge_extras
import notes_bridge_notes
import notes_docx_export
import notes_email_draft
import notes_highlights
import notes_review_marks
from scan_jobs import composition
from scan_jobs.auth import AuthError
from voice import note_repository

PREFIX = "/api/notes-bridge/v1"
_PATH = re.compile(r"^/notes(?:/(?P<filename>[^/]+))?$")
_EXPORT_PATH = re.compile(r"^/notes/(?P<filename>[^/]+)/export\.docx$")
_EMAIL_PATH = re.compile(r"^/notes/(?P<filename>[^/]+)/email-draft$")
_HIGHLIGHTS_PATH = re.compile(r"^/notes/(?P<filename>[^/]+)/highlights$")
_RENAME_PATH = re.compile(r"^/notes/(?P<filename>[^/]+)/rename$")
_DELETE_PATH = re.compile(r"^/notes/(?P<filename>[^/]+)/delete$")
_TRASH_LIST_PATH = re.compile(r"^/trash$")
_TRASH_RESTORE_PATH = re.compile(r"^/trash/(?P<filename>[^/]+)/restore$")
_TRASH_PURGE_PATH = re.compile(r"^/trash/(?P<filename>[^/]+)/purge$")
_TASK = re.compile(r"^t_[0-9a-f]{8,64}$")


def approved_path() -> Path:
    return Path(os.environ.get("NOTES_BRIDGE_APPROVED")
                or Path.home() / ".config" / "startrek_notes" / "approved.json")


def protected_path() -> Path:
    return Path(os.environ.get("NOTES_BRIDGE_PROTECTED")
                or Path.home() / ".config" / "startrek_notes" / "protected.json")


def approved_notes() -> "frozenset[str] | None":
    """The notes the Bridge may operate on. ``None`` means every note the
    repository exposes (``{"all": true}`` in the approved-notes file); a
    ``frozenset`` is the legacy per-filename allowlist. A missing or
    unreadable list approves nothing -- fails closed either way."""
    try:
        data = json.loads(approved_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    if isinstance(data, dict) and data.get("all") is True:
        return None
    names = data.get("notes", []) if isinstance(data, dict) else []
    return frozenset(name for name in names if isinstance(name, str) and name)


def protected_notes() -> frozenset[str]:
    """Filenames the Bridge may read but never write, rename, or delete.
    Missing list protects none."""
    try:
        data = json.loads(protected_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    names = data.get("notes", []) if isinstance(data, dict) else []
    return frozenset(name for name in names if isinstance(name, str) and name)


def in_scope(filename: str, approved: "frozenset[str] | None") -> bool:
    """Whether `filename` is a note the Bridge may operate on under `approved`."""
    return bool(filename) and (approved is None or filename in approved)


def _json(code: int, payload: object) -> tuple[int, bytes]:
    return code, json.dumps(payload).encode()


def dispatch(method: str, path: str, headers: dict[str, str], client_ip: str,
             body: bytes = b"") -> tuple[int, bytes]:
    """Return ``(status, JSON bytes)`` for one authenticated Bridge request."""
    parsed = urlparse(path)
    if not parsed.path.startswith(PREFIX):
        return _json(404, {"error": "not found"})
    suffix = parsed.path[len(PREFIX):]

    trash_list_match = _TRASH_LIST_PATH.match(suffix)
    trash_restore_match = _TRASH_RESTORE_PATH.match(suffix)
    trash_purge_match = _TRASH_PURGE_PATH.match(suffix)
    export_match = _EXPORT_PATH.match(suffix)
    email_match = _EMAIL_PATH.match(suffix)
    highlights_match = _HIGHLIGHTS_PATH.match(suffix)
    rename_match = _RENAME_PATH.match(suffix)
    delete_match = _DELETE_PATH.match(suffix)
    sub_match = export_match or email_match or highlights_match or rename_match or delete_match
    main_match = None if sub_match else _PATH.match(suffix)
    any_match = main_match or sub_match or trash_list_match or trash_restore_match or trash_purge_match
    if not any_match:
        return _json(404, {"error": "not found"})
    named_match = main_match or sub_match or trash_restore_match or trash_purge_match
    filename = (named_match.group("filename") or "") if named_match else ""

    task_header = headers.get("x-bridge-task", "")
    task = task_header if _TASK.match(task_header) else ""

    def log(event: str, *, filename: str = "", **fields: str) -> None:
        notes_activity.record(event, task_id=task, filename=filename, **fields)

    scope = "notes:write" if method == "POST" else "notes:read"
    try:
        actor = composition.authorizer().authorize(client_ip, headers, scope)
    except AuthError as exc:
        log("auth_failed", detail=f"{exc.code} ({exc.http}) for {scope}")
        return _json(exc.http, {"error": exc.code, "message": str(exc)})

    approved = approved_notes()
    repository = note_repository.build_note_repository()

    try:
        if trash_list_match:
            if method != "GET":
                return _json(405, {"error": "method_not_allowed"})
            status, payload, event, fields = notes_bridge_notes.list_trash(repository)
            log(event, actor=actor, **fields)
            return _json(status, payload)

        if trash_purge_match:
            if method != "POST":
                return _json(405, {"error": "method_not_allowed"})
            status, payload, event, fields = notes_bridge_extras.purge(repository, filename, body)
            log(event, actor=actor, **fields)
            return _json(status, payload)

        if trash_restore_match:
            if method != "POST":
                return _json(405, {"error": "method_not_allowed"})
            status, payload, event, fields = notes_bridge_notes.restore(repository, filename, body)
            log(event, actor=actor, **fields)
            return _json(status, payload)

        if export_match or email_match or highlights_match:
            if method != "GET":
                return _json(405, {"error": "method_not_allowed"})
            if not in_scope(filename, approved):
                log("not_approved", filename=filename, actor=actor, detail="not on the approved list")
                return _json(403, {"error": "note_not_approved",
                                   "message": "the Bridge reads and updates in-scope notes only"})
            note = repository.read(filename)
            revision = repository.revision(filename)
            if export_match:
                docx_bytes = notes_docx_export.build_docx_bytes(note)
                log("export_docx", filename=filename, actor=actor, revision=revision,
                    detail=f"{len(docx_bytes)} bytes")
                return _json(200, {"ok": True, "filename": filename, "revision": revision,
                                   "docx_base64": base64.b64encode(docx_bytes).decode("ascii")})
            if highlights_match:
                highlights = notes_highlights.highlights_payload(note)
                marks = notes_review_marks.review_marks(filename, note)
                log("highlights", filename=filename, actor=actor, revision=revision,
                    detail=f"{len(highlights)} span(s), {len(marks)} review mark(s)")
                return _json(200, {"ok": True, "filename": filename, "revision": revision,
                                   "highlights": highlights, "review_marks": marks})
            draft = notes_email_draft.build_email_draft(filename, note)
            log("email_draft", filename=filename, actor=actor, revision=revision)
            return _json(200, {"ok": True, "filename": filename, "revision": revision, **draft})

        if rename_match or delete_match:
            if method != "POST":
                return _json(405, {"error": "method_not_allowed"})
            if not in_scope(filename, approved):
                log("not_approved", filename=filename, actor=actor, detail="not on the approved list")
                return _json(403, {"error": "note_not_approved",
                                   "message": "the Bridge reads and updates in-scope notes only"})
            if filename in protected_notes():
                event = "protected"
                log(event, filename=filename, actor=actor,
                    detail="rename refused: note is protected" if rename_match
                    else "delete refused: note is protected")
                return _json(403, {"error": "note_protected",
                                   "message": "this note is protected; rename/delete are refused "
                                              "until it is explicitly unprotected"})
            if rename_match:
                status, payload, event, fields = notes_bridge_notes.rename(repository, filename, body)
            else:
                status, payload, event, fields = notes_bridge_notes.delete(repository, filename, body)
            log(event, actor=actor, **fields)
            return _json(status, payload)

        if method == "GET" and not filename and notes_bridge_extras.wants_search(parsed.query):
            status, payload, event, fields = notes_bridge_extras.search(repository, approved, parsed.query)
            log(event, actor=actor, **fields)
            return _json(status, payload)

        if method == "GET" and not filename:
            status, payload, event, fields = notes_bridge_core.list_notes(repository, approved)
            log(event, actor=actor, **fields)
            return _json(status, payload)

        if method == "POST" and not filename:
            status, payload, event, fields = notes_bridge_notes.create(repository, body)
            log(event, actor=actor, **fields)
            return _json(status, payload)

        if not in_scope(filename, approved):
            log("not_approved", filename=filename, actor=actor, detail="not on the approved list")
            return _json(403, {"error": "note_not_approved",
                               "message": "the Bridge reads and updates in-scope notes only"})

        if method == "GET":
            status, payload, event, fields = notes_bridge_core.read_note(repository, filename)
            log(event, actor=actor, **fields)
            return _json(status, payload)

        if method != "POST":
            return _json(405, {"error": "method_not_allowed"})

        if filename in protected_notes():
            log("protected", filename=filename, actor=actor, detail="write refused: note is protected")
            return _json(403, {"error": "note_protected",
                               "message": "this note is protected; writes are refused "
                                          "until it is explicitly unprotected"})
        status, payload, event, fields = notes_bridge_core.write_note(repository, filename, body)
        log(event, actor=actor, **fields)
        return _json(status, payload)
    except json.JSONDecodeError:
        return _json(400, {"error": "invalid_json"})
    except FileNotFoundError:
        log("error", filename=filename, detail="note not found")
        return _json(404, {"error": "note_not_found"})
    except (OSError, ValueError) as exc:
        log("error", filename=filename, detail=type(exc).__name__)
        return _json(400, {"error": str(exc)})
