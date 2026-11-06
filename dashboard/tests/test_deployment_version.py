import json

from monitoring import deployment_version


def test_uses_explicit_deployed_sha_from_environment(monkeypatch):
    monkeypatch.setenv("DASHBOARD_DEPLOYED_COMMIT_SHA", "A1B2C3D4E5F6")
    assert deployment_version.deployed_version() == {
        "deployed_sha": "a1b2c3d", "version_label": "a1b2c3d", "source": "environment"}


def test_reads_deployment_metadata_without_using_source_head(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHBOARD_DEPLOYED_COMMIT_SHA", raising=False)
    path = tmp_path / "version.json"
    path.write_text(json.dumps({"deployed_commit_sha": "1234567890abcdef"}))
    monkeypatch.setenv("DASHBOARD_DEPLOYMENT_METADATA", str(path))
    assert deployment_version.deployed_version()["deployed_sha"] == "1234567"


def test_missing_or_invalid_metadata_is_unknown(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHBOARD_DEPLOYED_COMMIT_SHA", raising=False)
    monkeypatch.setenv("DASHBOARD_DEPLOYMENT_METADATA", str(tmp_path / "missing"))
    result = deployment_version.deployed_version()
    assert result["deployed_sha"] is None
    assert result["version_label"] == "version unknown"
