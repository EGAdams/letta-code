"""list/read/write handlers for notes_bridge.py.

These are the three operations the facade has always had, factored out of
``dispatch`` so that function stays a router: match a route, check auth and
scope, call a handler, log and return. Same ``(status, payload, event,
fields)`` shape ``notes_bridge_notes.py``'s create/rename/delete/restore
handlers use, for the same reason -- one logging call site in
``notes_bridge.py``, regardless of which operation ran.
"""
from __future__ import annotations

import json


def list_notes(repository, approved: "frozenset[str] | None"):
    names = repository.list()
    if approved is not None:
        names = [name for name in names if name in approved]
    return 200, {"ok": True, "notes": names}, "list", {"detail": f"{len(names)} note(s) in scope"}


def read_note(repository, filename: str):
    note = repository.read(filename)
    revision = repository.revision(filename)
    payload = {"ok": True, "filename": filename, "note": note, "revision": revision}
    return (200, payload, "read",
            {"filename": filename, "revision": revision, "detail": f"{len(note.encode())} bytes"})


def write_note(repository, filename: str, body: bytes):
    data = json.loads(body or b"{}")
    note = data.get("note", "")
    expected_revision = data.get("expected_revision", "")
    requested = data.get("filename", filename)
    if not all(isinstance(value, str) for value in (note, requested, expected_revision)):
        return (400, {"error": "filename, note, and expected_revision must be strings"},
                "error", {"filename": filename, "detail": "bad write body"})
    if requested != filename:
        return (400, {"error": "filename in the body must match the path"},
                "error", {"filename": filename, "detail": "filename mismatch"})
    if not note.strip():
        return 400, {"error": "note must not be blank"}, "error", {"filename": filename, "detail": "blank write"}
    if not expected_revision:
        return (428, {"error": "revision_required", "message": "read the note first and send its revision"},
                "refused", {"filename": filename, "detail": "write without a revision"})
    try:
        revision = repository.write(filename, note, expected_revision)
    except FileExistsError:
        current = repository.revision(filename)
        return (409, {"error": "note_changed", "message": "note changed since it was read",
                      "filename": filename, "revision": current},
                "conflict", {"filename": filename, "expected_revision": expected_revision, "revision": current})
    payload = {"ok": True, "filename": filename, "revision": revision}
    return (200, payload, "write",
            {"filename": filename, "expected_revision": expected_revision, "revision": revision,
             "detail": f"{len(note.encode())} bytes"})
