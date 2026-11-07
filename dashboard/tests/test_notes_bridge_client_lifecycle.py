"""The script client and CLI over the real server: search, rename/move, delete, restore, purge."""
import json

import pytest

import notes_bridge_client as nbc
import notes_bridge_extras as extras
from scripts import chatgpt_notes_cli as cli
from tests.test_notes_bridge_client import TOKEN, live_server, notes_dir  # noqa: F401  (fixtures)


def test_client_manages_a_note_end_to_end(live_server, notes_dir):
    client = nbc.NotesBridgeClient(base_url=live_server, token=TOKEN)
    name, revision = client.create("find the NEEDLE\n", "scratch")
    assert [e["filename"] for e in client.search("needle")] == [name]

    moved = name.replace("_scratch", "_04-scratch")
    renamed = client.rename(name, revision, moved)
    assert renamed["filename"] == moved and [e["category"] for e in client.search(category=4)] == [4]

    trashed = client.delete(moved, renamed["revision"])["trashed_as"]
    assert client.trash_list() == [trashed] and not notes_dir.joinpath(moved).exists()
    assert client.restore(trashed)["restored_as"] == moved
    again = client.delete(moved, client.read(moved)[1])["trashed_as"]

    with pytest.raises(nbc.NotesBridgeError, match="403"):
        client.purge(again, "do it")
    assert client.trash_list() == [again]
    assert client.purge(again, extras.purge_phrase(again))["purged"] is True
    assert client.trash_list() == []


def test_cli_search_and_purge_guard(live_server, notes_dir, monkeypatch, capsys):
    monkeypatch.setenv("NOTES_BRIDGE_TOKEN", TOKEN)

    def run(*argv):
        code = cli.main(["--base-url", live_server, *argv])
        return code, json.loads(capsys.readouterr().out.strip().splitlines()[-1])   # the test server also logs to stdout

    code, found = run("search", "unmodified")          # the fixture deed text is "deed" content
    assert code == 0 and found["ok"] is True
    code, body = run("purge", "20261107120000_nothing.md", "--authorization", "x")
    assert code == 1 and body["ok"] is False
