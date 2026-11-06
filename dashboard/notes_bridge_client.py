"""The Bridge adapter notes_bridge.py's own docstring says doesn't exist yet.

A ChatGPT Bridge task that needs to read or edit a dashboard note talks to
``/api/notes-bridge/v1`` (see notes_bridge.py) through this client rather than
hand-rolling HTTP calls. It follows the same read-before-write discipline the
browser's own Notes page (js/boot/notes.js) already uses: a write always
carries the revision a prior read returned, so a Bridge edit can never
silently clobber a newer change made somewhere else -- including the browser's
own autosave.

Loopback-only and token-protected, same as every other scan-bridge client (see
scan_jobs/auth.py) -- this module does not relax either check, and never logs
or persists the bearer token. Provision a token first with
scripts/provision_notes_bridge_client.py, then export it as NOTES_BRIDGE_TOKEN
wherever this client runs.

No separate "trigger refresh" call exists or is needed: the Notes page polls
every 5s (js/boot/notes.js pollSelected) and picks up any revision change,
Bridge-authored or not.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://127.0.0.1:8765"
PREFIX = "/api/notes-bridge/v1"


class NotesBridgeError(Exception):
    """A /api/notes-bridge/v1 call failed; message always names the HTTP status."""


class NotesBridgeConfigError(NotesBridgeError):
    """No token is configured. Fail closed rather than send an unauthenticated request."""


class NoteNotFoundError(NotesBridgeError):
    pass


class NoteConflictError(NotesBridgeError):
    """The note changed on the dashboard since it was last read (HTTP 409)."""

    def __init__(self, message: str, revision: str | None = None):
        super().__init__(message)
        self.revision = revision


class NoteTextMatchError(NotesBridgeError):
    """``remove_text``'s target text was missing or ambiguous; it never guesses which occurrence."""


class NotesBridgeClient:
    """The one place a ChatGPT Bridge task reaches into the dashboard's notes."""

    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or os.environ.get("NOTES_BRIDGE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.token = token if token is not None else os.environ.get("NOTES_BRIDGE_TOKEN", "")
        if not self.token:
            raise NotesBridgeConfigError(
                "NOTES_BRIDGE_TOKEN is not set. Provision a client with "
                "scripts/provision_notes_bridge_client.py and export the token "
                "it prints once before using NotesBridgeClient.")

    def _call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{PREFIX}{path}", data=data, method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode())
            except (ValueError, OSError):
                payload = {}
            return exc.code, payload

    def _raise_for(self, status: int, payload: dict) -> None:
        message = f"HTTP {status}: {payload.get('message') or payload.get('error') or 'notes bridge request failed'}"
        if status == 404:
            raise NoteNotFoundError(message)
        if status == 409:
            raise NoteConflictError(message, revision=payload.get("revision"))
        raise NotesBridgeError(message)

    def list_notes(self) -> list[str]:
        status, payload = self._call("GET", "/notes")
        if status != 200:
            self._raise_for(status, payload)
        return payload.get("notes", [])

    def read(self, filename: str) -> tuple[str, str]:
        """Read one note. Returns (note_text, revision) -- the revision a later write must present."""
        status, payload = self._call("GET", f"/notes/{filename}")
        if status != 200:
            self._raise_for(status, payload)
        return payload["note"], payload["revision"]

    def create(self, note: str) -> tuple[str, str]:
        """Create a new note; the repository assigns the filename. Returns (filename, revision)."""
        status, payload = self._call("POST", "/notes", {"note": note})
        if status != 200:
            self._raise_for(status, payload)
        return payload["filename"], payload["revision"]

    def create_and_verify(self, note: str) -> tuple[str, str, str]:
        """Create, then read back the persisted text: (filename, note_text, revision)."""
        filename, _ = self.create(note)
        persisted_note, persisted_revision = self.read(filename)
        return filename, persisted_note, persisted_revision

    def write(self, filename: str, note: str, expected_revision: str | None = None) -> str:
        """Write an existing note, revision-checked against the dashboard's current copy.

        Reads the current revision first when the caller doesn't already have
        one, so a Bridge write always carries a revision read moments earlier
        rather than one assumed stale.
        """
        if expected_revision is None:
            _, expected_revision = self.read(filename)
        status, payload = self._call("POST", f"/notes/{filename}", {
            "filename": filename, "note": note, "expected_revision": expected_revision,
        })
        if status != 200:
            self._raise_for(status, payload)
        return payload["revision"]

    def write_and_verify(self, filename: str, note: str, expected_revision: str | None = None) -> tuple[str, str]:
        """Write, then read back the persisted text: the full read / revision-check / write / read-back contract."""
        self.write(filename, note, expected_revision)
        return self.read(filename)

    def remove_text(self, filename: str, text: str, expected_revision: str | None = None) -> tuple[str, str]:
        """Delete one exact, unique occurrence of ``text`` from a note. Returns (new_note_text, revision).

        Reads the note fresh, requires ``text`` to occur exactly once (raising
        ``NoteTextMatchError`` rather than guessing which occurrence otherwise),
        and writes the result back carrying that same read's revision -- a
        narrower, lower-risk edit than overwriting the whole note body for a
        single deletion.
        """
        note, revision = self.read(filename)
        if expected_revision is not None and expected_revision != revision:
            raise NoteConflictError(
                f"HTTP 409: note changed since expected_revision was read "
                f"(expected {expected_revision!r}, found {revision!r})", revision=revision)
        occurrences = note.count(text)
        if occurrences != 1:
            raise NoteTextMatchError(
                f"text occurs {occurrences} time(s) in {filename!r}; expected exactly 1")
        new_note = note.replace(text, "", 1)
        new_revision = self.write(filename, new_note, revision)
        return new_note, new_revision

    def remove_text_and_verify(self, filename: str, text: str, expected_revision: str | None = None) -> tuple[str, str]:
        """remove_text, then read back the persisted text: the full round trip."""
        self.remove_text(filename, text, expected_revision)
        return self.read(filename)

    def export_docx(self, filename: str) -> bytes:
        """The note rendered as a minimal .docx. Read-only; writes nothing."""
        status, payload = self._call("GET", f"/notes/{filename}/export.docx")
        if status != 200:
            self._raise_for(status, payload)
        return base64.b64decode(payload["docx_base64"])

    def email_draft(self, filename: str) -> dict:
        """{"subject", "body_text", "mailto_url"} for a human to send themselves.

        Nothing here sends mail -- see notes_email_draft.py for why no send
        path exists at all.
        """
        status, payload = self._call("GET", f"/notes/{filename}/email-draft")
        if status != 200:
            self._raise_for(status, payload)
        return {key: payload[key] for key in ("subject", "body_text", "mailto_url")}

    def highlights(self, filename: str) -> list[dict]:
        """Every persisted {{highlight:name}} span in the note. Read-only; writes nothing.

        Each item is {"text", "color", "line", "start", "end",
        "context_before", "context_after"}, recomputed from the note's
        current saved text (see notes_highlights.py) -- never a stored range
        that could drift from it. Excludes the deed page's view-only review
        marks (js/boot/notes.js deedReviewKind), which are not saved markup,
        and has no way to see an unsaved browser selection.
        """
        status, payload = self._call("GET", f"/notes/{filename}/highlights")
        if status != 200:
            self._raise_for(status, payload)
        return payload["highlights"]
