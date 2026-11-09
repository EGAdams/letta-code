"""Create/rename/delete/trash/restore handlers for notes_bridge.py.

notes_bridge.py owns authentication, scope (approved/protected lists), route
matching, and activity logging. Each function here does one thing against
the repository and returns ``(status, payload, event, log_fields)`` --
``dispatch`` logs ``event`` with ``log_fields`` (never note text) and returns
``payload`` at ``status``, the same shape the pre-existing list/read/write
code already produces, so every operation shows up on Worker Activity the
same way.

``FileNotFoundError`` (no such note) and the plain ``FileExistsError`` a
stale revision raises are left to propagate -- ``notes_bridge.dispatch``'s
own ``except`` block already turns those into 404 and a logged 409,
respectively, the same way it does for the pre-existing ``write``. Only
``note_repository.NoteNameConflictError`` (the target name is already taken)
is handled here, because it is a 409 with a different, non-generic message.
"""
from __future__ import annotations

import json

from voice.note_repository import NoteNameConflictError


def create(repository, body: bytes):
    data = json.loads(body or b"{}")
    note = data.get("note", "")
    filename_hint = data.get("filename", "")
    if not isinstance(note, str) or not isinstance(filename_hint, str):
        return (400, {"error": "note and filename must be strings"},
                "error", {"detail": "bad create body"})
    if not note.strip():
        return 400, {"error": "note must not be blank"}, "error", {"detail": "blank create"}
    saved = repository.save(note, filename_hint)
    revision = repository.revision(saved.filename)
    payload = {"ok": True, "filename": saved.filename, "revision": revision}
    return (200, payload, "create",
            {"filename": saved.filename, "revision": revision, "detail": f"{len(note.encode())} bytes"})


def rename(repository, filename: str, body: bytes):
    data = json.loads(body or b"{}")
    new_filename = data.get("new_filename", "")
    expected_revision = data.get("expected_revision", "")
    if not isinstance(new_filename, str) or not isinstance(expected_revision, str):
        return (400, {"error": "new_filename and expected_revision must be strings"},
                "error", {"filename": filename, "detail": "bad rename body"})
    if not new_filename.strip():
        return (400, {"error": "new_filename must not be blank"},
                "error", {"filename": filename, "detail": "blank rename target"})
    if not expected_revision:
        return (428, {"error": "revision_required", "message": "read the note first and send its revision"},
                "refused", {"filename": filename, "detail": "rename without a revision"})
    try:
        revision = repository.rename(filename, new_filename, expected_revision)
    except NoteNameConflictError:
        return (409, {"error": "name_exists", "message": f"{new_filename} already exists",
                      "filename": new_filename},
                "conflict", {"filename": filename, "detail": f"rename target {new_filename} already exists"})
    except FileExistsError:
        current = repository.revision(filename)
        return (409, {"error": "note_changed", "message": "note changed since it was read",
                      "filename": filename, "revision": current},
                "conflict", {"filename": filename, "expected_revision": expected_revision, "revision": current})
    payload = {"ok": True, "filename": new_filename, "previous_filename": filename, "revision": revision}
    return (200, payload, "rename",
            {"filename": filename, "revision": revision, "detail": f"renamed to {new_filename}"})


def delete(repository, filename: str, body: bytes):
    data = json.loads(body or b"{}")
    expected_revision = data.get("expected_revision", "")
    if not isinstance(expected_revision, str):
        return (400, {"error": "expected_revision must be a string"},
                "error", {"filename": filename, "detail": "bad delete body"})
    if not expected_revision:
        return (428, {"error": "revision_required", "message": "read the note first and send its revision"},
                "refused", {"filename": filename, "detail": "delete without a revision"})
    try:
        trashed_as = repository.delete(filename, expected_revision)
    except FileExistsError:
        current = repository.revision(filename)
        return (409, {"error": "note_changed", "message": "note changed since it was read",
                      "filename": filename, "revision": current},
                "conflict", {"filename": filename, "expected_revision": expected_revision, "revision": current})
    payload = {"ok": True, "filename": filename, "trashed_as": trashed_as}
    return 200, payload, "delete", {"filename": filename, "detail": f"trashed as {trashed_as}"}


def list_trash(repository):
    names = repository.list_trash()
    return 200, {"ok": True, "trash": names}, "list_trash", {"detail": f"{len(names)} trashed note(s)"}


def restore(repository, trashed_name: str, body: bytes):
    data = json.loads(body or b"{}")
    restored_filename = data.get("filename", "")
    if not isinstance(restored_filename, str):
        return (400, {"error": "filename must be a string"},
                "error", {"filename": trashed_name, "detail": "bad restore body"})
    try:
        restored_as = repository.restore(trashed_name, restored_filename)
    except NoteNameConflictError as exc:
        return (409, {"error": "name_exists", "message": f"{exc} already exists", "filename": str(exc)},
                "conflict", {"filename": trashed_name, "detail": f"restore target {exc} already exists"})
    revision = repository.revision(restored_as)
    payload = {"ok": True, "restored_as": restored_as, "revision": revision}
    return (200, payload, "restore",
            {"filename": trashed_name, "revision": revision, "detail": f"restored as {restored_as}"})
