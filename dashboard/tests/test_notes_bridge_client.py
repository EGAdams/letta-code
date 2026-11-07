"""End-to-end coverage for the Bridge adapter: a real DashboardHandler on a real
socket, a real TokenAuthorizer reading a throwaway clients.json, and a real
FilesystemNoteRepository reading/writing a throwaway notes directory -- nothing
here is mocked except the location of those two files, which conftest's
`_isolate_scan_jobs` already repoints per test.

Deliberately never writes to a file named deed.md: that name is reserved here
to prove the Bridge's read path returns probate deed content unmodified,
the same guarantee the live NOTES_DIR deed must have.
"""
import hashlib
import json
import os
import stat

import pytest

import notes_bridge_client as nbc
from scan_jobs import composition
from tests.http_app_harness import start_server

TOKEN = "integration-test-token-not-a-secret"
DEED_TEXT = "deed text that must not change\n"


def _provision(monkeypatch, tmp_path, scopes=("notes:read", "notes:write"), name="chatgpt-notes-bridge"):
    config_dir = tmp_path / "scan_bridge_config"
    config_dir.mkdir(exist_ok=True)
    clients_path = config_dir / "clients.json"
    clients_path.write_text(json.dumps({"clients": [{
        "name": name,
        "token_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
        "scopes": list(scopes),
    }]}))
    os.chmod(clients_path, stat.S_IRUSR | stat.S_IWUSR)
    monkeypatch.setenv("SCAN_BRIDGE_CONFIG_DIR", str(config_dir))
    composition.reset()


@pytest.fixture
def notes_dir(tmp_path, monkeypatch):
    from voice import config as voice_config
    directory = tmp_path / "notes"
    directory.mkdir()
    (directory / "deed.md").write_text(DEED_TEXT)
    monkeypatch.setattr(voice_config, "NOTES_DIR", str(directory))
    # The façade reaches approved notes only; here every note in the test directory is approved.
    import notes_bridge
    monkeypatch.setattr(notes_bridge, "approved_notes", lambda: frozenset(p.name for p in directory.iterdir()))
    monkeypatch.setenv("NOTES_ACTIVITY_LOG", str(tmp_path / "notes_activity.jsonl"))
    return directory


@pytest.fixture
def live_server(notes_dir, monkeypatch, tmp_path):
    _provision(monkeypatch, tmp_path)
    httpd, _thread, port = start_server()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        composition.reset()


def test_bridge_reads_deed_text_unmodified(live_server, notes_dir):
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)
    note, revision = client.read("deed.md")
    assert note == DEED_TEXT
    assert revision
    # The read is a GET; the file on disk is untouched either way.
    assert notes_dir.joinpath("deed.md").read_text() == DEED_TEXT


def test_bridge_lists_existing_notes_without_changing_them(live_server, notes_dir):
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)
    assert client.list_notes() == ["deed.md"]
    assert notes_dir.joinpath("deed.md").read_text() == DEED_TEXT


def test_bridge_create_needs_a_name_and_never_overwrites(live_server, notes_dir):
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    with pytest.raises(nbc.NotesBridgeError, match="400"):
        client.create("brand new note")  # no name: refused, nothing written
    assert sorted(p.name for p in notes_dir.iterdir()) == ["deed.md"]

    first, _ = client.create("one", name="Plans", category=5)
    second, _ = client.create("two", name="Plans", category=5)
    assert first != second and "_05-plans" in first
    assert notes_dir.joinpath("deed.md").read_text() == DEED_TEXT


def test_bridge_manages_a_note_end_to_end(live_server, notes_dir):
    import notes_library
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)
    name, revision = client.create("find the NEEDLE\n", name="Scratch")
    assert [e["filename"] for e in client.search("needle")] == [name]

    moved = client.rename(name, revision, category=4)
    assert moved["filename"].endswith("_04-scratch.md") and not notes_dir.joinpath(name).exists()
    gone = client.trash(moved["filename"], moved["revision"])
    assert [t["trash_id"] for t in client.trash_list()] == [gone["trash_id"]]
    assert notes_dir.joinpath(moved["filename"]).exists() is False

    back = client.restore(gone["trash_id"])
    assert notes_dir.joinpath(back["filename"]).read_text() == "find the NEEDLE\n"

    again = client.trash(back["filename"], back["revision"])
    with pytest.raises(nbc.NotesBridgeError, match="403"):
        client.purge(again["trash_id"], "do it")
    assert client.trash_list()
    assert client.purge(again["trash_id"], notes_library.purge_phrase(again["trash_id"]))["purged"]
    assert client.trash_list() == []


def test_bridge_refuses_a_note_that_is_not_approved(live_server, notes_dir, monkeypatch):
    import notes_bridge
    monkeypatch.setattr(notes_bridge, "approved_notes", lambda: frozenset())
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    with pytest.raises(nbc.NotesBridgeError, match="403"):
        client.read("deed.md")
    assert client.list_notes() == []


def test_bridge_write_then_read_back_persists_exactly(live_server, notes_dir):
    notes_dir.joinpath("sample.md").write_text("v1\n")
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    persisted_note, persisted_revision = client.write_and_verify("sample.md", "v2")

    assert persisted_note == "v2\n"
    assert notes_dir.joinpath("sample.md").read_text() == "v2\n"
    # Read-back is independent of the write call's own return value.
    assert client.read("sample.md") == (persisted_note, persisted_revision)
    # The unrelated deed note is never touched by someone else's write.
    assert notes_dir.joinpath("deed.md").read_text() == DEED_TEXT


def test_bridge_write_auto_reads_revision_when_not_supplied(live_server, notes_dir):
    notes_dir.joinpath("sample.md").write_text("v1\n")
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    client.write("sample.md", "v2")  # no expected_revision: client reads it first

    assert notes_dir.joinpath("sample.md").read_text() == "v2\n"


def test_bridge_write_conflict_is_rejected_and_file_unchanged(live_server, notes_dir):
    notes_dir.joinpath("sample.md").write_text("original\n")
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    with pytest.raises(nbc.NoteConflictError):
        client.write("sample.md", "clobbered", expected_revision="stale-revision")

    assert notes_dir.joinpath("sample.md").read_text() == "original\n"


def test_bridge_write_to_unknown_note_is_not_found(live_server, notes_dir, monkeypatch):
    import notes_bridge
    monkeypatch.setattr(notes_bridge, "approved_notes", lambda: frozenset({"missing.md"}))
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)
    with pytest.raises(nbc.NoteNotFoundError):
        client.write("missing.md", "text", expected_revision="whatever")


def test_bridge_remove_text_deletes_one_unique_occurrence(live_server, notes_dir):
    notes_dir.joinpath("sample.md").write_text("Grantee [marital status to be confirmed] here\n")
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    new_note, revision = client.remove_text("sample.md", "[marital status to be confirmed] ")

    assert new_note == "Grantee here\n"
    assert revision
    assert notes_dir.joinpath("sample.md").read_text() == "Grantee here\n"
    # The unrelated deed note is never touched by someone else's edit.
    assert notes_dir.joinpath("deed.md").read_text() == DEED_TEXT


def test_bridge_remove_text_and_verify_reads_back_the_result(live_server, notes_dir):
    notes_dir.joinpath("sample.md").write_text("before [placeholder] after\n")
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    persisted_note, revision = client.remove_text_and_verify("sample.md", "[placeholder] ")

    assert persisted_note == "before after\n"
    assert client.read("sample.md") == (persisted_note, revision)


def test_bridge_remove_text_rejects_missing_text_without_writing(live_server, notes_dir):
    notes_dir.joinpath("sample.md").write_text("no brackets here\n")
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    with pytest.raises(nbc.NoteTextMatchError):
        client.remove_text("sample.md", "[missing]")

    assert notes_dir.joinpath("sample.md").read_text() == "no brackets here\n"


def test_bridge_remove_text_rejects_ambiguous_text_without_writing(live_server, notes_dir):
    notes_dir.joinpath("sample.md").write_text("[x] and another [x]\n")
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    with pytest.raises(nbc.NoteTextMatchError):
        client.remove_text("sample.md", "[x]")

    assert notes_dir.joinpath("sample.md").read_text() == "[x] and another [x]\n"


def test_bridge_remove_text_rejects_stale_expected_revision_without_writing(live_server, notes_dir):
    notes_dir.joinpath("sample.md").write_text("Grantee [marital status] here\n")
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    with pytest.raises(nbc.NoteConflictError):
        client.remove_text("sample.md", "[marital status] ", expected_revision="stale-revision")

    assert notes_dir.joinpath("sample.md").read_text() == "Grantee [marital status] here\n"


def test_bridge_rejects_a_missing_token(live_server):
    with pytest.raises(nbc.NotesBridgeConfigError):
        nbc.NotesBridgeClient(base_url=live_server, token="")


def test_bridge_rejects_a_wrong_token(live_server):
    client = nbc.NotesBridgeClient(base_url=live_server, token="wrong-token")
    with pytest.raises(nbc.NotesBridgeError) as err:
        client.list_notes()
    assert "HTTP 401" in str(err.value)


def test_bridge_export_docx_returns_bytes_and_writes_nothing(live_server, notes_dir):
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    data = client.export_docx("deed.md")

    assert data.startswith(b"PK")  # a .docx is a zip archive
    assert notes_dir.joinpath("deed.md").read_text() == DEED_TEXT


def test_bridge_email_draft_strips_markup_and_writes_nothing(live_server, notes_dir):
    notes_dir.joinpath("deed.md").write_text("{{color:red}}Warning:{{/color}} review this\n")
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    draft = client.email_draft("deed.md")

    assert draft["body_text"] == "Warning: review this"
    assert draft["mailto_url"].startswith("mailto:")
    assert notes_dir.joinpath("deed.md").read_text() == "{{color:red}}Warning:{{/color}} review this\n"


def test_bridge_highlights_returns_persisted_spans_and_writes_nothing(live_server, notes_dir):
    notes_dir.joinpath("deed.md").write_text(
        "Personal Representative's Deed\n\n"
        "{{highlight:yellow}}verify the legal description{{/highlight}} before filing.\n")
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)

    highlights = client.highlights("deed.md")

    assert [h["text"] for h in highlights] == ["verify the legal description"]
    assert highlights[0]["color"] == "yellow"
    assert highlights[0]["context_after"].startswith(" before filing.")
    assert notes_dir.joinpath("deed.md").read_text() == (
        "Personal Representative's Deed\n\n"
        "{{highlight:yellow}}verify the legal description{{/highlight}} before filing.\n")


def test_bridge_highlights_on_unmarked_note_is_empty(live_server, notes_dir):
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)
    assert client.highlights("deed.md") == []


def test_bridge_enforces_scope(monkeypatch, tmp_path, notes_dir):
    _provision(monkeypatch, tmp_path, scopes=("notes:read",))
    httpd, _thread, port = start_server()
    try:
        client = nbc.NotesBridgeClient(base_url=f"http://127.0.0.1:{port}", token=TOKEN)
        assert client.read("deed.md")[0] == DEED_TEXT
        with pytest.raises(nbc.NotesBridgeError) as err:
            client.write("deed.md", "nope", expected_revision="whatever")
        assert "HTTP 403" in str(err.value)
        assert notes_dir.joinpath("deed.md").read_text() == DEED_TEXT
    finally:
        httpd.shutdown()
        composition.reset()
