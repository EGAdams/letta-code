import json

from monitoring import agent_bridge_poll, model_registry, worker_activity, worker_restart


def test_snapshot_uses_default_path_when_environment_is_not_set(tmp_path, monkeypatch):
    path = tmp_path / "worker_activity.json"
    path.write_text(json.dumps([{"id": "task-1", "status": "running"}]))
    monkeypatch.setattr(worker_activity, "DEFAULT_SNAPSHOT", path)
    monkeypatch.delenv("WORKER_ACTIVITY_SNAPSHOT", raising=False)

    tasks, error, updated_at, stale = worker_activity._snapshot()

    assert tasks == [{"id": "task-1", "status": "running"}]
    assert error is None
    assert updated_at is not None
    assert stale is False


def test_snapshot_marks_old_ledger_without_changing_task_state(tmp_path, monkeypatch):
    path = tmp_path / "worker_activity.json"
    path.write_text(json.dumps([{"id": "task-1", "status": "succeeded"}]))
    monkeypatch.setattr(worker_activity, "DEFAULT_SNAPSHOT", path)
    monkeypatch.delenv("WORKER_ACTIVITY_SNAPSHOT", raising=False)
    monkeypatch.setattr(worker_activity.time, "time", lambda: path.stat().st_mtime + 61)

    tasks, error, _updated_at, stale = worker_activity._snapshot()

    assert tasks[0]["status"] == "succeeded"
    assert error is None
    assert stale is True


def test_payload_round_trips_the_service_dict_from_agent_bridge_poll(tmp_path, monkeypatch):
    """payload() rebuilds a ServiceState from agent_bridge_poll's own dumped dict
    (`ServiceState(**service)`); a field mismatch between the two would raise
    inside the /api/worker-activity route instead of here."""
    monkeypatch.setattr(worker_activity, "DEFAULT_SNAPSHOT", tmp_path / "missing.json")
    monkeypatch.delenv("WORKER_ACTIVITY_SNAPSHOT", raising=False)
    service = agent_bridge_poll.ServiceState(active="active", pid=4242)
    monkeypatch.setattr(agent_bridge_poll, "agent_bridge_poll_payload", lambda *_lane: {
        "polling": "active", "reason": "polling",
        "service": service.model_dump(mode="json"),
        "state": {"heartbeat_at": 1000}, "now": 1000.0,
    })
    monkeypatch.setattr(worker_restart, "configured", lambda: False)

    result = worker_activity.payload()

    assert result["ok"] is True
    assert result["tasks_available"] is False
    assert result["diagnostic"]["status"] in {"healthy", "offline", "stalled", "unknown"}
    assert result["worker"]["service"]["pid"] == 4242
    assert [lane["lane"] for lane in result["workers"]] == ["general", "express"]


def test_escalation_is_honestly_unavailable_without_a_supervisor_state_file(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_activity, "DEFAULT_ESCALATION_STATE", tmp_path / "missing.json")
    monkeypatch.delenv("ADW_SUPERVISOR_STATE_PATH", raising=False)

    result = worker_activity._escalation()

    assert result["available"] is False
    assert "has not written a state file" in result["reason"]


def test_escalation_reads_the_independent_supervisor_state_file(tmp_path, monkeypatch):
    path = tmp_path / "adw_supervisor_state.json"
    path.write_text(json.dumps({
        "generated_at": worker_activity.time.time(), "source": "verified-local-ledger",
        "alerts": [{"task_id": "t1", "tier": "recommend"}],
    }))
    monkeypatch.setattr(worker_activity, "DEFAULT_ESCALATION_STATE", path)
    monkeypatch.delenv("ADW_SUPERVISOR_STATE_PATH", raising=False)
    monkeypatch.setattr(worker_activity.time, "time", lambda: path.stat().st_mtime + 1)

    result = worker_activity._escalation()

    assert result["available"] is True
    assert result["stale"] is False
    assert result["alerts"] == [{"task_id": "t1", "tier": "recommend"}]


def test_escalation_flags_a_stale_supervisor_heartbeat(tmp_path, monkeypatch):
    path = tmp_path / "adw_supervisor_state.json"
    path.write_text(json.dumps({"generated_at": 1000.0}))
    monkeypatch.setattr(worker_activity, "DEFAULT_ESCALATION_STATE", path)
    monkeypatch.delenv("ADW_SUPERVISOR_STATE_PATH", raising=False)
    monkeypatch.setattr(worker_activity.time, "time", lambda: path.stat().st_mtime + worker_activity.ESCALATION_STALE_SECONDS + 1)

    result = worker_activity._escalation()

    assert result["available"] is True
    assert result["stale"] is True
    assert "older than expected" in result["reason"]


def test_payload_includes_a_verified_provider_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_activity, "DEFAULT_SNAPSHOT", tmp_path / "missing.json")
    monkeypatch.delenv("WORKER_ACTIVITY_SNAPSHOT", raising=False)
    monkeypatch.setattr(worker_activity, "DEFAULT_ESCALATION_STATE", tmp_path / "missing-state.json")
    monkeypatch.setattr(worker_restart, "configured", lambda: False)
    monkeypatch.setattr(model_registry, "registry", lambda *a, **k: [
        {"id": "claude-sonnet", "label": "Claude Sonnet", "available": True},
    ])

    result = worker_activity.payload()

    assert result["provider_selection"] == {
        "current": "",
        "providers": [{"id": "claude-sonnet", "label": "Claude Sonnet", "available": True, "configured": False, "detail": ""}],
    }


def test_escalation_rejects_nonfinite_heartbeat_and_malformed_alerts(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setenv("ADW_SUPERVISOR_STATE_PATH", str(path))
    for value in ({"heartbeat_at": float("nan")}, {"alerts": {"wrong": "shape"}}):
        path.write_text(json.dumps(value))
        assert worker_activity._escalation()["available"] is False


def test_copying_old_state_does_not_refresh_supervisor_heartbeat(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"heartbeat_at": 1000, "alerts": []}))
    monkeypatch.setenv("ADW_SUPERVISOR_STATE_PATH", str(path))
    monkeypatch.setattr(worker_activity.time, "time", lambda: 2000)
    assert worker_activity._escalation()["stale"] is True
