import json

from monitoring import model_registry


def _write_config(tmp_path, entries):
    path = tmp_path / "model_registry.json"
    path.write_text(json.dumps(entries))
    return path


def test_cli_probe_reports_configured_only_when_binary_is_on_path(monkeypatch):
    monkeypatch.setattr(model_registry.shutil, "which", lambda name: "/usr/bin/" + name if name == "codex" else None)

    present = model_registry._verify_cli("codex")
    missing = model_registry._verify_cli("nonexistent-cli-xyz")

    assert present.available is False
    assert present.status == "configured"
    assert missing.available is False
    assert missing.status == "unconfigured"


def test_credentials_probe_never_reads_file_contents(tmp_path):
    cred = tmp_path / ".credentials.json"
    cred.write_text("not valid json at all {{{")

    health = model_registry._verify_credentials(str(cred))

    assert health.available is False
    assert health.status == "configured"


def test_credentials_probe_reports_unconfigured_when_missing(tmp_path):
    health = model_registry._verify_credentials(str(tmp_path / "missing.json"))

    assert health.available is False
    assert health.status == "unconfigured"


def test_none_probe_is_always_unavailable():
    health = model_registry._verify_none("no check exists yet")

    assert health.available is False
    assert health.status == "unconfigured"
    assert health.detail == "no check exists yet"


def test_registry_never_marks_unverifiable_entries_available(tmp_path):
    path = _write_config(tmp_path, [
        {"id": "astra", "label": "Astra", "verify_kind": "none", "verify_arg": "unverified"},
    ])

    rows = model_registry.registry(path)

    assert rows == [{
        "id": "astra", "label": "Astra", "task_capabilities": [], "can_write": False,
        "cost_tier": "unknown", "dispatch_strategy": "unavailable", "available": False,
        "status": "unconfigured", "configured": False, "verification": "runtime-unverified", "detail": "unverified", "checked_at": rows[0]["checked_at"],
    }]


def test_registry_reflects_a_real_local_cli_probe(tmp_path, monkeypatch):
    path = _write_config(tmp_path, [
        {"id": "codex", "label": "Codex", "verify_kind": "cli", "verify_arg": "codex",
         "task_capabilities": ["diagnose"], "cost_tier": "low", "dispatch_strategy": "secondary"},
    ])
    monkeypatch.setattr(model_registry.shutil, "which", lambda name: "/usr/local/bin/codex")

    rows = model_registry.registry(path)

    assert rows[0]["available"] is False
    assert rows[0]["status"] == "configured"


def test_malformed_config_yields_an_empty_registry_not_a_crash(tmp_path):
    path = tmp_path / "model_registry.json"
    path.write_text("not json")

    assert model_registry.registry(path) == []


def test_provider_selection_payload_matches_the_renderer_contract(tmp_path, monkeypatch):
    path = _write_config(tmp_path, [
        {"id": "codex", "label": "Codex", "verify_kind": "cli", "verify_arg": "codex"},
        {"id": "claude-sonnet", "label": "Claude Sonnet", "verify_kind": "credentials",
         "verify_arg": str(tmp_path / "missing-creds.json")},
    ])
    monkeypatch.setattr(model_registry.shutil, "which", lambda name: "/usr/local/bin/codex")

    payload = model_registry.provider_selection_payload(current="codex", path=path)

    assert payload == {
        "current": "codex",
        "providers": [
            {"id": "codex", "label": "Codex", "available": False, "configured": True, "detail": payload["providers"][0]["detail"]},
            {"id": "claude-sonnet", "label": "Claude Sonnet", "available": False, "configured": False, "detail": payload["providers"][1]["detail"]},
        ],
    }


def test_register_probe_is_a_plugin_point(tmp_path):
    path = _write_config(tmp_path, [
        {"id": "custom", "label": "Custom", "verify_kind": "always-on", "verify_arg": ""},
    ])
    model_registry.register_probe("always-on", lambda arg: model_registry.ModelHealth(True, "configured", "stub", 0.0))

    rows = model_registry.registry(path)

    assert rows[0]["available"] is True
    del model_registry.VERIFY_PROBES["always-on"]
