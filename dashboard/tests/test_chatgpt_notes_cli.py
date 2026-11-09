"""Smoke test: scripts/chatgpt_notes_cli.py must import its dashboard-level
notes_bridge_client even when run directly, from any cwd, without PYTHONPATH.

Also the full CLI<->Bridge API contract: list/read/create/update against a
real DashboardHandler on a real socket (see tests/http_app_harness.py), the
revision-conflict fail-closed path, and the bearer token never leaking into
output.
"""
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from scan_jobs import composition
from scripts import chatgpt_notes_cli as cli
from tests.http_app_harness import start_server

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "chatgpt_notes_cli.py"
TOKEN = "integration-test-token-not-a-secret"


def _provision(monkeypatch, tmp_path):
    config_dir = tmp_path / "scan_bridge_config"
    config_dir.mkdir(exist_ok=True)
    clients_path = config_dir / "clients.json"
    clients_path.write_text(json.dumps({"clients": [{
        "name": "chatgpt-notes-bridge",
        "token_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
        "scopes": ["notes:read", "notes:write"],
    }]}))
    os.chmod(clients_path, stat.S_IRUSR | stat.S_IWUSR)
    monkeypatch.setenv("SCAN_BRIDGE_CONFIG_DIR", str(config_dir))
    composition.reset()


@pytest.fixture
def notes_dir(tmp_path, monkeypatch):
    from voice import config as voice_config
    directory = tmp_path / "notes"
    directory.mkdir()
    (directory / "existing.md").write_text("v1\n")
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


def _run(monkeypatch, capsys, base_url, argv, stdin_text=None, token=TOKEN):
    if token is None:
        monkeypatch.delenv("NOTES_BRIDGE_TOKEN", raising=False)
    else:
        monkeypatch.setenv("NOTES_BRIDGE_TOKEN", token)
    if stdin_text is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    returncode = cli.main(["--base-url", base_url, *argv])
    # The in-process server writes its access log to stdout too; the CLI's JSON is the last line.
    body = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return returncode, body


def test_list_returns_existing_filenames(live_server, notes_dir, monkeypatch, capsys):
    returncode, body = _run(monkeypatch, capsys, live_server, ["list"])
    assert returncode == 0
    assert body["notes"] == ["existing.md"]


def test_read_returns_note_and_revision(live_server, notes_dir, monkeypatch, capsys):
    returncode, body = _run(monkeypatch, capsys, live_server, ["read", "existing.md"])
    assert returncode == 0
    assert body["note"] == "v1\n"
    assert body["revision"]


def test_create_is_refused_and_writes_nothing(live_server, notes_dir, monkeypatch, capsys):
    returncode, body = _run(monkeypatch, capsys, live_server, ["create"], stdin_text="fresh note")
    assert returncode == 1
    assert body["ok"] is False
    assert sorted(p.name for p in notes_dir.iterdir()) == ["existing.md"]


def test_update_with_correct_revision_succeeds_and_verifies(live_server, notes_dir, monkeypatch, capsys):
    _, read_body = _run(monkeypatch, capsys, live_server, ["read", "existing.md"])
    returncode, body = _run(
        monkeypatch, capsys, live_server,
        ["update", "existing.md", "--expected-revision", read_body["revision"]],
        stdin_text="v2",
    )
    assert returncode == 0
    assert body["verified"] is True
    assert notes_dir.joinpath("existing.md").read_text() == "v2\n"


def test_update_with_stale_revision_fails_closed_and_leaves_file_unchanged(live_server, notes_dir, monkeypatch, capsys):
    returncode, body = _run(
        monkeypatch, capsys, live_server,
        ["update", "existing.md", "--expected-revision", "stale-revision"],
        stdin_text="clobbered",
    )
    assert returncode == 1
    assert body["error"] == "NoteConflictError"
    assert body["revision"]
    assert notes_dir.joinpath("existing.md").read_text() == "v1\n"


def test_update_without_expected_revision_is_rejected_by_argument_parsing(live_server, notes_dir, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("v2"))
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--base-url", live_server, "update", "existing.md"])
    assert excinfo.value.code == 2


def test_remove_text_deletes_one_occurrence_and_strips_trailing_newline(live_server, notes_dir, monkeypatch, capsys):
    notes_dir.joinpath("deed.md").write_text("Grantee [marital status to be confirmed] here\n")
    _, read_body = _run(monkeypatch, capsys, live_server, ["read", "deed.md"])
    returncode, body = _run(
        monkeypatch, capsys, live_server,
        ["remove-text", "deed.md", "--expected-revision", read_body["revision"]],
        stdin_text="[marital status to be confirmed] \n",
    )
    assert returncode == 0
    assert body["removed"] is True
    assert notes_dir.joinpath("deed.md").read_text() == "Grantee here\n"


def test_remove_text_with_missing_text_fails_closed_and_leaves_file_unchanged(live_server, notes_dir, monkeypatch, capsys):
    _, read_body = _run(monkeypatch, capsys, live_server, ["read", "existing.md"])
    returncode, body = _run(
        monkeypatch, capsys, live_server,
        ["remove-text", "existing.md", "--expected-revision", read_body["revision"]],
        stdin_text="[not present]",
    )
    assert returncode == 1
    assert body["error"] == "NoteTextMatchError"
    assert notes_dir.joinpath("existing.md").read_text() == "v1\n"


def test_remove_text_with_stale_revision_fails_closed_and_leaves_file_unchanged(live_server, notes_dir, monkeypatch, capsys):
    returncode, body = _run(
        monkeypatch, capsys, live_server,
        ["remove-text", "existing.md", "--expected-revision", "stale-revision"],
        stdin_text="v1",
    )
    assert returncode == 1
    assert body["error"] == "NoteConflictError"
    assert notes_dir.joinpath("existing.md").read_text() == "v1\n"


def test_remove_text_without_expected_revision_is_rejected_by_argument_parsing(live_server, notes_dir, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("[x]"))
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--base-url", live_server, "remove-text", "existing.md"])
    assert excinfo.value.code == 2


def test_highlights_returns_persisted_spans_and_writes_nothing(live_server, notes_dir, monkeypatch, capsys):
    notes_dir.joinpath("deed.md").write_text(
        "{{highlight:yellow}}verify the legal description{{/highlight}} before filing.\n")
    returncode, body = _run(monkeypatch, capsys, live_server, ["highlights", "deed.md"])
    assert returncode == 0
    assert body["filename"] == "deed.md"
    [highlight] = body["highlights"]
    assert highlight["text"] == "verify the legal description"
    assert highlight["color"] == "yellow"
    assert notes_dir.joinpath("deed.md").read_text() == (
        "{{highlight:yellow}}verify the legal description{{/highlight}} before filing.\n")


def test_highlights_on_unmarked_note_is_empty_list(live_server, notes_dir, monkeypatch, capsys):
    returncode, body = _run(monkeypatch, capsys, live_server, ["highlights", "existing.md"])
    assert returncode == 0
    assert body["highlights"] == []


def test_missing_token_fails_closed_before_any_request(live_server, notes_dir, monkeypatch, capsys):
    returncode, body = _run(monkeypatch, capsys, live_server, ["list"], token=None)
    assert returncode == 2
    assert body["error"] == "NotesBridgeConfigError"
    assert TOKEN not in json.dumps(body)


def test_output_never_contains_the_bearer_token(live_server, notes_dir, monkeypatch, capsys):
    returncode, body = _run(monkeypatch, capsys, live_server, ["read", "existing.md"])
    assert returncode == 0
    assert TOKEN not in json.dumps(body)


def test_help_runs_from_another_cwd_without_pythonpath(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "ModuleNotFoundError" not in result.stderr
