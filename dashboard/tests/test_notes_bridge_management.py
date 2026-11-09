"""Scope, revisions and protection for the Notes bridge's management routes, through dispatch.

Written against the current contract (create by `filename` hint, `/notes/<f>/delete` to the trash,
`/trash/<id>/restore`). Search, purge and highlights are covered in test_notes_bridge_extras.py."""
import json

import pytest

import notes_bridge
from voice import note_repository

PREFIX = "/api/notes-bridge/v1"


class Auth:
    def authorize(self, client_ip, headers, scope):
        return "agent-bridge-notes"


@pytest.fixture
def world(tmp_path, monkeypatch):
    notes = tmp_path / "notes"
    notes.mkdir()
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "approved.json").write_text(json.dumps({"all": True}))
    monkeypatch.setenv("NOTES_BRIDGE_APPROVED", str(cfg / "approved.json"))
    monkeypatch.setenv("NOTES_BRIDGE_PROTECTED", str(cfg / "protected.json"))
    monkeypatch.setenv("NOTES_ACTIVITY_LOG", str(tmp_path / "activity.jsonl"))
    monkeypatch.setattr(notes_bridge.composition, "authorizer", lambda: Auth())
    monkeypatch.setattr(notes_bridge.note_repository, "build_note_repository",
                        lambda: note_repository.FilesystemNoteRepository(str(notes)))

    def call(method, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        status, raw = notes_bridge.dispatch(method, PREFIX + path, {"authorization": "Bearer t"},
                                            "127.0.0.1", body)
        return status, json.loads(raw)
    call.cfg, call.notes = cfg, notes
    return call


def make(call, hint="alpha", text="hello"):
    status, body = call("POST", "/notes", {"note": text, "filename": hint})
    assert status == 200, body
    return body


def test_all_mode_reaches_notes_nobody_listed(world):
    (world.notes / "2026-01-01_old.md").write_text("old\n")
    status, body = world("GET", "/notes")
    assert status == 200 and "2026-01-01_old.md" in body["notes"]
    status, body = world("GET", "/notes/2026-01-01_old.md")
    assert status == 200 and body["note"] == "old\n"


def test_without_all_mode_the_list_still_gates(world):
    world.cfg.joinpath("approved.json").write_text(json.dumps({"notes": ["2026-01-01_a.md"]}))
    (world.notes / "2026-01-01_a.md").write_text("a\n")
    (world.notes / "2026-01-01_b.md").write_text("b\n")
    assert world("GET", "/notes")[1]["notes"] == ["2026-01-01_a.md"]
    assert world("GET", "/notes/2026-01-01_b.md")[0] == 403


def test_all_must_be_true_not_merely_truthy(world):
    world.cfg.joinpath("approved.json").write_text(json.dumps({"all": "yes"}))
    (world.notes / "2026-01-01_b.md").write_text("b\n")
    assert world("GET", "/notes/2026-01-01_b.md")[0] == 403


def test_rename_requires_the_current_revision(world):
    made = make(world, "draft", "body")
    path = f"/notes/{made['filename']}/rename"
    target = made["filename"].replace("_draft", "_04-draft")
    assert world("POST", path, {"new_filename": target})[0] in (400, 428)
    status, body = world("POST", path, {"new_filename": target, "expected_revision": "0" * 64})
    assert status == 409
    status, body = world("POST", path, {"new_filename": target, "expected_revision": made["revision"]})
    assert status == 200 and body["filename"] == target
    assert world("GET", f"/notes/{made['filename']}")[0] == 404


def test_protected_notes_cannot_be_renamed_or_deleted_even_in_all_mode(world):
    made = make(world, "deed", "legal")
    world.cfg.joinpath("protected.json").write_text(json.dumps({"notes": [made["filename"]]}))
    for action, extra in (("delete", {}), ("rename", {"new_filename": "2026-01-01_x.md"})):
        status, body = world("POST", f"/notes/{made['filename']}/{action}",
                             {"expected_revision": made["revision"], **extra})
        assert status == 403, (action, body)
    assert world("GET", f"/notes/{made['filename']}")[0] == 200


def test_a_deleted_note_is_in_the_trash_not_the_browser_list_and_comes_back(world):
    made = make(world, "hidden", "x")
    trashed = world("POST", f"/notes/{made['filename']}/delete", {"expected_revision": made["revision"]})[1]["trashed_as"]
    repo = note_repository.FilesystemNoteRepository(str(world.notes))
    assert repo.list() == [] and world("GET", "/trash")[1]["trash"] == [trashed]
    status, back = world("POST", f"/trash/{trashed}/restore", {})
    assert status == 200 and world("GET", f"/notes/{made['filename']}")[0] == 200
