"""Search, permanent delete, review marks -- on top of the create/rename/delete/restore routes -- through dispatch."""
import json

import pytest

import notes_bridge
import notes_bridge_extras as extras
from voice import note_repository

PREFIX = "/api/notes-bridge/v1"
DEED = "2026-11-03_draft-personal-representative-s-deed-of-distribution.md"


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
        status, raw = notes_bridge.dispatch(method, PREFIX + path, {"authorization": "Bearer t"}, "127.0.0.1", body)
        return status, json.loads(raw)
    call.notes, call.cfg = notes, cfg
    return call


def make(world, hint, text="hello"):
    status, body = world("POST", "/notes", {"note": text, "filename": hint})
    assert status == 200, body
    return body


def test_search_by_text_name_and_category(world):
    a = make(world, "04-probate", "the NEEDLE is here\nsecond line")
    make(world, "05-agents", "nothing relevant")
    status, body = world("GET", "/notes?q=needle")
    assert status == 200 and body["notes"] == [a["filename"]]
    assert body["entries"][0]["matches"][0] == {"line": 1, "text": "the NEEDLE is here"}
    assert body["entries"][0]["revision"] == a["revision"]
    assert [e["category"] for e in world("GET", "/notes?category=5")[1]["entries"]] == [5]
    assert world("GET", "/notes?q=probate")[1]["notes"] == [a["filename"]]          # a name match
    assert world("GET", "/notes?category=abc")[0] == 400


def test_the_plain_list_is_unchanged(world):
    a = make(world, "plain")
    status, body = world("GET", "/notes")
    assert body == {"ok": True, "notes": [a["filename"]]}


def test_a_category_move_is_a_rename_and_search_follows_it(world):
    made = make(world, "draft", "body")
    moved = world("POST", f"/notes/{made['filename']}/rename",
                  {"new_filename": made["filename"].replace("_draft", "_04-draft"), "expected_revision": made["revision"]})[1]
    assert extras.category_of(moved["filename"]) == 4
    assert [e["filename"] for e in world("GET", "/notes?category=4")[1]["entries"]] == [moved["filename"]]


def test_purge_only_from_the_trash_and_only_with_the_exact_sentence(world):
    made = make(world, "doomed", "bye")
    name = made["filename"]
    # a live note is not purgeable, even with the right words
    status, body = world("POST", f"/trash/{name}/purge", {"authorization": extras.purge_phrase(name)})
    assert status == 400 and (world.notes / name).exists()

    trashed = world("POST", f"/notes/{name}/delete", {"expected_revision": made["revision"]})[1]["trashed_as"]
    for wrong in ("", "yes", "go ahead", extras.purge_phrase("another.md")):
        status, body = world("POST", f"/trash/{trashed}/purge", {"authorization": wrong})
        assert status == 403 and body["error"] == "authorization_required"
    assert world("GET", "/trash")[1]["trash"] == [trashed]

    status, body = world("POST", f"/trash/{trashed}/purge", {"authorization": extras.purge_phrase(trashed)})
    assert status == 200 and body["purged"] is True
    assert world("GET", "/trash")[1]["trash"] == [] and not (world.notes / name).exists()
    assert world("POST", f"/trash/{trashed}/purge", {"authorization": extras.purge_phrase(trashed)})[0] == 404


def test_purge_cannot_escape_the_trash(world):
    for bad in ("..%2Fsecret.md", "x.md", "20261107120000_..%2F..%2Fetc.md"):
        status, _ = world("POST", f"/trash/{bad}/purge", {"authorization": "x"})
        assert status in (400, 404)


def test_highlights_report_saved_spans_and_the_decks_review_marks(world):
    (world.notes / DEED).write_text("# Personal Representative's Deed of Distribution\n"
                                    "{{highlight:yellow}}see this{{/highlight}}\nParcel No. [VERIFY]\n")
    status, body = world("GET", f"/notes/{DEED}/highlights")
    assert [h["text"] for h in body["highlights"]] == ["see this"]
    assert [(m["line"], m["kind"]) for m in body["review_marks"]] == [(3, "legal-description")]
    (world.notes / "plain.md").write_text("[VERIFY] but not the deed\n")
    assert world("GET", "/notes/plain.md/highlights")[1]["review_marks"] == []


def test_the_other_routes_still_work_through_the_hooks(world):
    made = make(world, "round", "one")
    status, body = world("POST", f"/notes/{made['filename']}", {"note": "two", "expected_revision": made["revision"]})
    assert status == 200
    back = world("GET", f"/notes/{made['filename']}")[1]
    assert back["note"] == "two\n"
    gone = world("POST", f"/notes/{made['filename']}/delete", {"expected_revision": back["revision"]})[1]["trashed_as"]
    restored = world("POST", f"/trash/{gone}/restore", {})[1]
    assert restored["restored_as"] == made["filename"]
