"""Token-protected agent façade for the dashboard's filesystem notes.

This is the HTTP contract the Star Trek Bridge worker's ``notes`` agent calls
(``agent_blocks/lancedb_memory/agent_bridge_worker/adapters/notes_bridge_http.py``);
``notes_bridge_client.py`` is the same contract for scripts. Browser routes
stay separate so their behaviour is unchanged.

Three rules hold here, on the server, whatever the client does:

* **Authorized.** Every call needs a scan-bridge bearer token with
  ``notes:read`` (GET) or ``notes:write`` (POST) -- ``scan_jobs/auth.py``.
* **Approved notes only.** A note is reachable only if its filename is listed
  in ``NOTES_BRIDGE_APPROVED`` (default ``~/.config/startrek_notes/approved.json``,
  ``{"notes": ["<filename>", ...]}``). A missing or unreadable list approves
  nothing. The façade never creates a note.
* **No blind overwrite.** A write carries the revision a read returned; a stale
  one is a 409 and nothing is written.
* **Protected notes are read-only here regardless of approval.** A filename
  in ``NOTES_BRIDGE_PROTECTED`` is still readable and still exportable, but
  every write to it is refused -- for a note (such as a legal document)
  whose corrections must be authorized some other way before this façade is
  allowed to touch it.

Three read-only derivations exist alongside read/write, all logged the same
way and requiring only ``notes:read``: ``GET .../export.docx`` renders the
note (Markdown plus the ``{{color:name}}``/``{{highlight:name}}`` spans
documented in ``notes_formatting``) as a minimal Word document, returned as
base64 JSON; ``GET .../email-draft`` returns a subject, a plain-text body
with markup stripped, and a ``mailto:`` link (neither ever sends mail or
writes a note -- see ``notes_email_draft`` for why no send path exists at
all); ``GET .../highlights`` returns every persisted ``{{highlight:name}}``
span -- exact text, color, line, character offsets, and surrounding context,
all recomputed from the note's current saved text by ``notes_highlights`` so
nothing here is a stored range that could drift -- which is what the Bridge
``notes`` agent calls to answer "what is highlighted in this note."

Every outcome -- read, write, conflict, refusal, authorization failure -- is
recorded by ``notes_activity`` (names and revisions only, never note text) for
the Worker Activity page. A caller may send ``X-Bridge-Task: t_<hex>`` so its
events group under its Bridge task.
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import notes_activity
import notes_docx_export
import notes_email_draft
import notes_highlights
from scan_jobs import composition
from scan_jobs.auth import AuthError
from voice import note_repository

PREFIX = "/api/notes-bridge/v1"
_PATH = re.compile(r"^/notes(?:/(?P<filename>[^/]+))?$")
_EXPORT_PATH = re.compile(r"^/notes/(?P<filename>[^/]+)/export\.docx$")
_EMAIL_PATH = re.compile(r"^/notes/(?P<filename>[^/]+)/email-draft$")
_HIGHLIGHTS_PATH = re.compile(r"^/notes/(?P<filename>[^/]+)/highlights$")
_TASK = re.compile(r"^t_[0-9a-f]{8,64}$")


def approved_path() -> Path:
    return Path(os.environ.get("NOTES_BRIDGE_APPROVED")
                or Path.home() / ".config" / "startrek_notes" / "approved.json")


def protected_path() -> Path:
    return Path(os.environ.get("NOTES_BRIDGE_PROTECTED")
                or Path.home() / ".config" / "startrek_notes" / "protected.json")


def approved_notes() -> frozenset[str]:
    """The filenames the Bridge may read and update. Fails closed to none."""
    try:
        data = json.loads(approved_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    names = data.get("notes", []) if isinstance(data, dict) else []
    return frozenset(name for name in names if isinstance(name, str) and name)


def protected_notes() -> frozenset[str]:
    """Filenames the Bridge may read but never write. Missing list protects none."""
    try:
        data = json.loads(protected_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    names = data.get("notes", []) if isinstance(data, dict) else []
    return frozenset(name for name in names if isinstance(name, str) and name)


def _json(code: int, payload: object) -> tuple[int, bytes]:
    return code, json.dumps(payload).encode()


def dispatch(method: str, path: str, headers: dict[str, str], client_ip: str,
             body: bytes = b"") -> tuple[int, bytes]:
    """Return ``(status, JSON bytes)`` for one authenticated Bridge request."""
    parsed = urlparse(path)
    if not parsed.path.startswith(PREFIX):
        return _json(404, {"error": "not found"})
    suffix = parsed.path[len(PREFIX):]
    export_match = _EXPORT_PATH.match(suffix)
    email_match = _EMAIL_PATH.match(suffix)
    highlights_match = _HIGHLIGHTS_PATH.match(suffix)
    sub_match = export_match or email_match or highlights_match
    match = None if sub_match else _PATH.match(suffix)
    if not match and not sub_match:
        return _json(404, {"error": "not found"})
    filename = (match or sub_match).group("filename") or ""
    task = headers.get("x-bridge-task", "")
    task = task if _TASK.match(task) else ""

    def log(event: str, **fields: str) -> None:
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
        if sub_match:
            if method != "GET":
                return _json(405, {"error": "method_not_allowed"})
            if filename not in approved:
                log("not_approved", actor=actor, detail="not on the approved list")
                return _json(403, {"error": "note_not_approved",
                                   "message": "the Bridge reads and updates approved notes only"})
            note = repository.read(filename)
            revision = repository.revision(filename)
            if export_match:
                docx_bytes = notes_docx_export.build_docx_bytes(note)
                log("export_docx", actor=actor, revision=revision,
                    detail=f"{len(docx_bytes)} bytes")
                return _json(200, {"ok": True, "filename": filename, "revision": revision,
                                   "docx_base64": base64.b64encode(docx_bytes).decode("ascii")})
            if highlights_match:
                highlights = notes_highlights.highlights_payload(note)
                log("highlights", actor=actor, revision=revision, detail=f"{len(highlights)} span(s)")
                return _json(200, {"ok": True, "filename": filename, "revision": revision,
                                   "highlights": highlights})
            draft = notes_email_draft.build_email_draft(filename, note)
            log("email_draft", actor=actor, revision=revision)
            return _json(200, {"ok": True, "filename": filename, "revision": revision, **draft})

        if method == "GET" and not filename:
            names = [name for name in repository.list() if name in approved]
            log("list", actor=actor, detail=f"{len(names)} approved note(s)")
            return _json(200, {"ok": True, "notes": names})
        if not filename or filename not in approved:
            log("not_approved", actor=actor,
                detail="create is not offered" if not filename else "not on the approved list")
            return _json(403, {"error": "note_not_approved",
                               "message": "the Bridge reads and updates approved notes only"})
        if method == "GET":
            note = repository.read(filename)
            revision = repository.revision(filename)
            log("read", actor=actor, revision=revision, detail=f"{len(note.encode())} bytes")
            return _json(200, {"ok": True, "filename": filename, "note": note,
                               "revision": revision})
        if method != "POST":
            return _json(405, {"error": "method_not_allowed"})
        if filename in protected_notes():
            log("protected", actor=actor, detail="write refused: note is protected")
            return _json(403, {"error": "note_protected",
                               "message": "this note is protected; writes are refused "
                                          "until it is explicitly unprotected"})
        data = json.loads(body or b"{}")
        note = data.get("note", "")
        expected_revision = data.get("expected_revision", "")
        requested = data.get("filename", filename)
        if not all(isinstance(value, str) for value in (note, requested, expected_revision)):
            return _json(400, {"error": "filename, note, and expected_revision must be strings"})
        if requested != filename:
            return _json(400, {"error": "filename in the body must match the path"})
        if not note.strip():
            return _json(400, {"error": "note must not be blank"})
        if not expected_revision:
            log("refused", actor=actor, detail="write without a revision")
            return _json(428, {"error": "revision_required",
                               "message": "read the note first and send its revision"})
        try:
            revision = repository.write(filename, note, expected_revision)
        except FileExistsError:
            current = repository.revision(filename)
            log("conflict", actor=actor, expected_revision=expected_revision, revision=current)
            return _json(409, {"error": "note_changed",
                               "message": "note changed since it was read",
                               "filename": filename, "revision": current})
        log("write", actor=actor, expected_revision=expected_revision, revision=revision,
            detail=f"{len(note.encode())} bytes")
        return _json(200, {"ok": True, "filename": filename, "revision": revision,
                           "actor": actor})
    except json.JSONDecodeError:
        return _json(400, {"error": "invalid_json"})
    except FileNotFoundError:
        log("error", detail="note not found")
        return _json(404, {"error": "note_not_found"})
    except (OSError, ValueError) as exc:
        log("error", detail=type(exc).__name__)
        return _json(400, {"error": str(exc)})
