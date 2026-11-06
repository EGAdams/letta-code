import json

import pytest

from notes_bridge import dispatch
from scan_jobs.auth import AuthError


class Repo:
    def __init__(self):
        self.text = "deed v1\n"
        self.rev = "r1"
        self.writes = 0

    def list(self):
        return ["private.md", "deed.md"]

    def read(self, filename):
        assert filename == "deed.md"
        return self.text

    def revision(self, filename):
        assert filename == "deed.md"
        return self.rev

    def write(self, filename, note, expected_revision):
        assert filename == "deed.md"
        if expected_revision != self.rev:
            raise FileExistsError(filename)
        self.writes += 1
        self.text = note if note.endswith("\n") else note + "\n"
        self.rev = "r2"
        return self.rev

    def save(self, note, filename=""):  # the façade must never create a note
        raise AssertionError("create is not offered")


class Auth:
    def authorize(self, client_ip, headers, scope):
        assert client_ip == "127.0.0.1"
        assert scope in {"notes:read", "notes:write"}
        return "agent-bridge-notes"


class Denied:
    def __init__(self, scope_needed=None):
        self.scope_needed = scope_needed

    def authorize(self, client_ip, headers, scope):
        if self.scope_needed and scope == self.scope_needed:
            raise AuthError("insufficient_scope", f"token lacks {scope}", 403)
        if not self.scope_needed:
            raise AuthError("unauthorized", "unknown token", 401)
        return "read-only-client"


@pytest.fixture
def activity(tmp_path, monkeypatch):
    log = tmp_path / "notes_activity.jsonl"
    approved = tmp_path / "approved.json"
    approved.write_text(json.dumps({"notes": ["deed.md"]}))
    monkeypatch.setenv("NOTES_ACTIVITY_LOG", str(log))
    monkeypatch.setenv("NOTES_BRIDGE_APPROVED", str(approved))

    def events():
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return events


def call(monkeypatch, method, path, payload=b"", auth=None, repo=None, task=""):
    import notes_bridge

    repo = repo or Repo()
    monkeypatch.setattr(notes_bridge.composition, "authorizer", lambda: auth or Auth())
    monkeypatch.setattr(notes_bridge.note_repository, "build_note_repository", lambda: repo)
    headers = {"authorization": "Bearer test"}
    if task:
        headers["x-bridge-task"] = task
    status, raw = dispatch(method, path, headers, "127.0.0.1", payload)
    return status, json.loads(raw), repo


def test_bridge_read_returns_exact_markdown_and_revision(monkeypatch, activity):
    status, body, _ = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes/deed.md",
                           task="t_0123456789abcdef")

    assert status == 200
    assert body == {"ok": True, "filename": "deed.md", "note": "deed v1\n", "revision": "r1"}
    [event] = activity()
    assert event["event"] == "read" and event["task_id"] == "t_0123456789abcdef"
    assert event["revision"] == "r1" and "deed v1" not in json.dumps(event)


def test_bridge_list_shows_only_approved_notes(monkeypatch, activity):
    status, body, _ = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes")
    assert status == 200 and body["notes"] == ["deed.md"]


def test_unapproved_note_is_refused_and_logged(monkeypatch, activity):
    import notes_bridge
    monkeypatch.setattr(notes_bridge, "approved_notes", lambda: frozenset())
    status, body, _ = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes/deed.md")
    assert status == 403 and body["error"] == "note_not_approved"
    assert activity()[-1]["event"] == "not_approved"


def test_missing_approval_list_approves_nothing(monkeypatch, activity, tmp_path):
    monkeypatch.setenv("NOTES_BRIDGE_APPROVED", str(tmp_path / "absent.json"))
    payload = json.dumps({"note": "x", "expected_revision": "r1"}).encode()
    status, body, repo = call(monkeypatch, "POST", "/api/notes-bridge/v1/notes/deed.md", payload)
    assert status == 403 and repo.writes == 0


def test_create_is_not_offered(monkeypatch, activity):
    payload = json.dumps({"note": "new note"}).encode()
    status, body, _ = call(monkeypatch, "POST", "/api/notes-bridge/v1/notes", payload)
    assert status == 403 and body["error"] == "note_not_approved"


def test_unknown_token_is_refused_and_logged(monkeypatch, activity):
    status, body, _ = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes/deed.md", auth=Denied())
    assert status == 401 and body["error"] == "unauthorized"
    event = activity()[-1]
    assert event["event"] == "auth_failed" and "401" in event["detail"]


def test_read_only_token_cannot_write(monkeypatch, activity):
    payload = json.dumps({"note": "changed", "expected_revision": "r1"}).encode()
    status, body, repo = call(monkeypatch, "POST", "/api/notes-bridge/v1/notes/deed.md", payload,
                              auth=Denied(scope_needed="notes:write"))
    assert status == 403 and body["error"] == "insufficient_scope"
    assert repo.text == "deed v1\n"
    assert activity()[-1]["event"] == "auth_failed"


def test_bridge_write_requires_revision_and_rejects_stale_edit(monkeypatch, activity):
    payload = json.dumps({"filename": "deed.md", "note": "changed"}).encode()
    status, body, _ = call(monkeypatch, "POST", "/api/notes-bridge/v1/notes/deed.md", payload)
    assert status == 428
    assert body["error"] == "revision_required"

    payload = json.dumps({"filename": "deed.md", "note": "changed", "expected_revision": "old"}).encode()
    status, body, repo = call(monkeypatch, "POST", "/api/notes-bridge/v1/notes/deed.md", payload)
    assert status == 409
    assert body["error"] == "note_changed" and body["revision"] == "r1"
    assert repo.text == "deed v1\n"
    conflict = activity()[-1]
    assert conflict["event"] == "conflict" and conflict["expected_revision"] == "old"


def test_body_filename_must_match_path(monkeypatch, activity):
    payload = json.dumps({"filename": "other.md", "note": "x", "expected_revision": "r1"}).encode()
    status, _, repo = call(monkeypatch, "POST", "/api/notes-bridge/v1/notes/deed.md", payload)
    assert status == 400 and repo.writes == 0


def test_bridge_write_returns_new_revision(monkeypatch, activity):
    payload = json.dumps({"filename": "deed.md", "note": "changed", "expected_revision": "r1"}).encode()
    status, body, repo = call(monkeypatch, "POST", "/api/notes-bridge/v1/notes/deed.md", payload)
    assert status == 200
    assert body["revision"] == "r2"
    assert repo.text == "changed\n"
    write = activity()[-1]
    assert write["event"] == "write" and write["revision"] == "r2" and write["expected_revision"] == "r1"


def test_export_docx_returns_base64_and_does_not_write(monkeypatch, activity):
    status, body, repo = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes/deed.md/export.docx")
    assert status == 200
    assert body["ok"] is True and body["filename"] == "deed.md" and body["revision"] == "r1"
    assert body["docx_base64"]
    assert repo.writes == 0
    assert activity()[-1]["event"] == "export_docx"


def test_export_docx_post_is_not_allowed(monkeypatch, activity):
    status, body, _ = call(monkeypatch, "POST", "/api/notes-bridge/v1/notes/deed.md/export.docx")
    assert status == 405 and body["error"] == "method_not_allowed"


def test_export_docx_refuses_an_unapproved_note(monkeypatch, activity):
    status, body, _ = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes/private.md/export.docx")
    assert status == 403 and body["error"] == "note_not_approved"
    assert activity()[-1]["event"] == "not_approved"


def test_email_draft_returns_subject_and_body_and_does_not_write(monkeypatch, activity):
    status, body, repo = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes/deed.md/email-draft")
    assert status == 200
    assert body["ok"] is True and body["revision"] == "r1"
    assert body["subject"] == "deed v1"
    assert body["body_text"] == "deed v1"
    assert body["mailto_url"].startswith("mailto:")
    assert repo.writes == 0
    assert activity()[-1]["event"] == "email_draft"


def test_email_draft_refuses_an_unapproved_note(monkeypatch, activity):
    status, body, _ = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes/private.md/email-draft")
    assert status == 403 and body["error"] == "note_not_approved"


class HighlightedRepo(Repo):
    def __init__(self):
        super().__init__()
        self.text = "{{highlight:yellow}}verify the legal description{{/highlight}}\n"

    def read(self, filename):
        assert filename == "deed.md"
        return self.text


def test_highlights_returns_persisted_spans_and_does_not_write(monkeypatch, activity):
    status, body, repo = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes/deed.md/highlights",
                              repo=HighlightedRepo())
    assert status == 200
    assert body["ok"] is True and body["filename"] == "deed.md" and body["revision"] == "r1"
    [highlight] = body["highlights"]
    assert highlight["text"] == "verify the legal description"
    assert highlight["color"] == "yellow"
    assert repo.writes == 0
    event = activity()[-1]
    assert event["event"] == "highlights" and "verify" not in json.dumps(event)


def test_highlights_post_is_not_allowed(monkeypatch, activity):
    status, body, _ = call(monkeypatch, "POST", "/api/notes-bridge/v1/notes/deed.md/highlights")
    assert status == 405 and body["error"] == "method_not_allowed"


def test_highlights_refuses_an_unapproved_note(monkeypatch, activity):
    status, body, _ = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes/private.md/highlights")
    assert status == 403 and body["error"] == "note_not_approved"


def test_highlights_on_a_note_with_no_markup_is_an_empty_list(monkeypatch, activity):
    status, body, _ = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes/deed.md/highlights")
    assert status == 200 and body["highlights"] == []


def test_protected_note_write_is_refused_and_logged(monkeypatch, activity, tmp_path):
    protected = tmp_path / "protected.json"
    protected.write_text(json.dumps({"notes": ["deed.md"]}))
    monkeypatch.setenv("NOTES_BRIDGE_PROTECTED", str(protected))
    payload = json.dumps({"filename": "deed.md", "note": "changed", "expected_revision": "r1"}).encode()
    status, body, repo = call(monkeypatch, "POST", "/api/notes-bridge/v1/notes/deed.md", payload)
    assert status == 403 and body["error"] == "note_protected"
    assert repo.writes == 0
    assert activity()[-1]["event"] == "protected"


def test_protected_note_is_still_readable(monkeypatch, activity, tmp_path):
    protected = tmp_path / "protected.json"
    protected.write_text(json.dumps({"notes": ["deed.md"]}))
    monkeypatch.setenv("NOTES_BRIDGE_PROTECTED", str(protected))
    status, body, _ = call(monkeypatch, "GET", "/api/notes-bridge/v1/notes/deed.md")
    assert status == 200 and body["note"] == "deed v1\n"


def test_missing_protected_list_protects_nothing(monkeypatch, activity, tmp_path):
    monkeypatch.setenv("NOTES_BRIDGE_PROTECTED", str(tmp_path / "absent.json"))
    payload = json.dumps({"filename": "deed.md", "note": "changed", "expected_revision": "r1"}).encode()
    status, body, repo = call(monkeypatch, "POST", "/api/notes-bridge/v1/notes/deed.md", payload)
    assert status == 200 and repo.writes == 1
