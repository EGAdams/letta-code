import json

import pytest

import notes_bridge
import notes_library
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
    monkeypatch.setattr(notes_bridge, "build_library", lambda: notes_library.NoteLibrary(str(notes)))
    monkeypatch.setattr(notes_bridge.note_repository, "build_note_repository",
                        lambda: note_repository.FilesystemNoteRepository(str(notes)))

    def call(method, path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        status, raw = notes_bridge.dispatch(method, PREFIX + path, {"authorization": "Bearer t"},
                                            "127.0.0.1", body)
        return status, json.loads(raw)
    call.cfg, call.notes = cfg, notes
    return call


def make(call, name="Alpha", text="hello", category=None):
    status, body = call("POST", "/notes", {"name": name, "note": text, "category": category})
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


def test_all_false_is_not_all(world):
    world.cfg.joinpath("approved.json").write_text(json.dumps({"all": "yes"}))
    (world.notes / "2026-01-01_b.md").write_text("b\n")
    assert world("GET", "/notes/2026-01-01_b.md")[0] == 403


def test_create_search_and_detail(world):
    made = make(world, "Probate Deed", "find the NEEDLE here", 4)
    assert made["category"] == 4
    status, body = world("GET", "/notes?q=needle")
    assert body["entries"][0]["filename"] == made["filename"]
    assert body["entries"][0]["matches"][0]["line"] == 1
    assert world("GET", "/notes?category=5")[1]["notes"] == []
    assert world("GET", "/notes?category=abc")[0] == 400


def test_rename_move_requires_the_current_revision(world):
    made = make(world, "Draft", "body", 1)
    path = f"/notes/{made['filename']}/rename"
    assert world("POST", path, {"category": 4})[0] == 428
    status, body = world("POST", path, {"expected_revision": "0" * 64, "category": 4})
    assert status == 409 and body["revision"] == made["revision"]
    status, body = world("POST", path, {"expected_revision": made["revision"], "category": 4})
    assert status == 200 and body["filename"].endswith("_04-draft.md")
    assert world("GET", f"/notes/{made['filename']}")[0] == 404


def test_trash_restore_and_the_purge_phrase(world):
    made = make(world, "Doomed", "bye")
    name = made["filename"]
    status, gone = world("POST", f"/notes/{name}/trash", {"expected_revision": made["revision"]})
    assert status == 200 and world("GET", f"/notes/{name}")[0] == 404
    assert world("GET", "/trash")[1]["trash"][0]["trash_id"] == gone["trash_id"]
    status, back = world("POST", f"/trash/{gone['trash_id']}/restore", {})
    assert status == 200 and back["filename"] == name

    again = world("POST", f"/notes/{name}/trash", {"expected_revision": back["revision"]})[1]
    bad = world("POST", f"/trash/{again['trash_id']}/purge", {"authorization": "yes please"})
    assert bad[0] == 403 and bad[1]["error"] == "authorization_required"
    assert world("GET", "/trash")[1]["trash"]
    phrase = notes_library.purge_phrase(again["trash_id"])
    status, done = world("POST", f"/trash/{again['trash_id']}/purge", {"authorization": phrase})
    assert status == 200 and done["purged"] and world("GET", "/trash")[1]["trash"] == []


def test_protected_notes_cannot_be_renamed_or_trashed_even_in_all_mode(world):
    made = make(world, "Deed", "legal")
    world.cfg.joinpath("protected.json").write_text(json.dumps({"notes": [made["filename"]]}))
    for action in ("trash", "rename"):
        status, body = world("POST", f"/notes/{made['filename']}/{action}",
                             {"expected_revision": made["revision"], "new_name": "x"})
        assert status == 403 and body["error"] == "note_protected"
    assert world("GET", f"/notes/{made['filename']}")[0] == 200


def test_highlights_route_reports_persisted_spans_and_review_marks(world):
    name = "2026-11-03_draft-personal-representative-s-deed-of-distribution.md"
    (world.notes / name).write_text("# Personal Representative's Deed of Distribution\n"
                                    "{{highlight:yellow}}see this{{/highlight}}\n"
                                    "Parcel No. [VERIFY]\n")
    status, body = world("GET", f"/notes/{name}/highlights")
    assert status == 200
    assert [h["text"] for h in body["highlights"]] == ["see this"]
    assert [(m["line"], m["kind"]) for m in body["review_marks"]] == [(3, "legal-description")]


def test_trash_listing_is_invisible_to_the_browser_note_list(world):
    made = make(world, "Hidden", "x")
    world("POST", f"/notes/{made['filename']}/trash", {"expected_revision": made["revision"]})
    repo = note_repository.FilesystemNoteRepository(str(world.notes))
    assert repo.list() == []
