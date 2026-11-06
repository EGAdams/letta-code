"""scripts/provision_notes_bridge_client.py: merge semantics, never overwrite,
mode 0600, and the printed token actually matches what gets hashed to disk."""
import hashlib
import json
import os
import stat

from scripts import provision_notes_bridge_client as provision


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_provisions_a_new_file_with_one_client(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SCAN_BRIDGE_CONFIG_DIR", str(tmp_path))
    rc = provision.main([])
    assert rc == 0

    path = tmp_path / "clients.json"
    data = _read(path)
    assert [c["name"] for c in data["clients"]] == ["chatgpt-notes-bridge"]
    assert data["clients"][0]["scopes"] == ["notes:read", "notes:write"]
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600

    lines = capsys.readouterr().out.strip().splitlines()
    token_line = next(i for i, line in enumerate(lines) if line.startswith("Token (shown once"))
    token = lines[token_line + 1]
    assert hashlib.sha256(token.encode()).hexdigest() == data["clients"][0]["token_sha256"]


def test_merges_without_touching_other_clients(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAN_BRIDGE_CONFIG_DIR", str(tmp_path))
    path = tmp_path / "clients.json"
    path.write_text(json.dumps({"clients": [{
        "name": "agent-bridge-worker",
        "token_sha256": "a" * 64,
        "scopes": ["scanner:status"],
    }]}))
    os.chmod(path, 0o600)

    rc = provision.main([])
    assert rc == 0

    data = _read(path)
    names = sorted(c["name"] for c in data["clients"])
    assert names == ["agent-bridge-worker", "chatgpt-notes-bridge"]
    worker = next(c for c in data["clients"] if c["name"] == "agent-bridge-worker")
    assert worker == {"name": "agent-bridge-worker", "token_sha256": "a" * 64, "scopes": ["scanner:status"]}


def test_refuses_a_duplicate_name_without_rotate(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SCAN_BRIDGE_CONFIG_DIR", str(tmp_path))
    rc = provision.main([])
    assert rc == 0
    before = (tmp_path / "clients.json").read_text()

    rc = provision.main([])
    assert rc == 1
    assert (tmp_path / "clients.json").read_text() == before
    assert "already exists" in capsys.readouterr().err


def test_rotate_replaces_only_its_own_token(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAN_BRIDGE_CONFIG_DIR", str(tmp_path))
    provision.main([])
    first_hash = _read(tmp_path / "clients.json")["clients"][0]["token_sha256"]

    rc = provision.main(["--rotate"])
    assert rc == 0

    data = _read(tmp_path / "clients.json")
    assert [c["name"] for c in data["clients"]] == ["chatgpt-notes-bridge"]
    assert data["clients"][0]["token_sha256"] != first_hash


def test_token_file_mode_writes_0600_file_and_never_prints_the_token(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SCAN_BRIDGE_CONFIG_DIR", str(tmp_path / "scan"))
    token_file = tmp_path / "startrek_notes" / "notes_token"
    rc = provision.main(["--name", "agent-bridge-notes", "--token-file", str(token_file)])
    assert rc == 0

    token = token_file.read_text(encoding="utf-8").strip()
    assert stat.S_IMODE(os.stat(token_file).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(token_file.parent).st_mode) == 0o700
    entry = _read(tmp_path / "scan" / "clients.json")["clients"][0]
    assert entry["name"] == "agent-bridge-notes"
    assert entry["scopes"] == ["notes:read", "notes:write"]
    assert hashlib.sha256(token.encode()).hexdigest() == entry["token_sha256"]
    assert token not in capsys.readouterr().out
