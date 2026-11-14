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


def test_payload_exposes_terminal_clear_epoch_without_changing_the_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_activity, "DEFAULT_SNAPSHOT", tmp_path / "missing.json")
    monkeypatch.setattr(worker_activity.terminal_clear, "DEFAULT_STATE", tmp_path / "clear.json")
    monkeypatch.setattr(worker_restart, "configured", lambda: False)
    result = worker_activity.payload()
    assert result["terminal_clear_epoch"] == 0
    assert not (tmp_path / "clear.json").exists()


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


def test_queue_depth_counts_a_task_waiting_only_at_the_gateway(tmp_path, monkeypatch):
    monkeypatch.setattr(worker_activity, "DEFAULT_SNAPSHOT", tmp_path / "missing.json")
    monkeypatch.delenv("WORKER_ACTIVITY_SNAPSHOT", raising=False)
    monkeypatch.setattr(agent_bridge_poll, "agent_bridge_poll_payload", lambda *_lane: {
        "polling": "active", "reason": "polling", "service": agent_bridge_poll.ServiceState().model_dump(mode="json"),
        "state": None, "now": 1.0})
    monkeypatch.setattr(worker_activity, "_escalation", lambda: {"available": True, "stale": False, "queued_count": 1})
    monkeypatch.setattr(worker_activity, "_snapshot", lambda: ([], None, 1.0, False))
    assert worker_activity.payload()["queue_depth"] == 1
    monkeypatch.setattr(worker_activity, "_escalation", lambda: {"available": True, "stale": True, "queued_count": 5})
    assert worker_activity.payload()["queue_depth"] == 0, "a stale supervisor never raises the count"


class _Supervision:
    def __init__(self, value=None, boom=False):
        self.calls, self.value, self.boom = 0, value, boom

    def supervision(self):
        self.calls += 1
        if self.boom:
            raise RuntimeError("gateway exploded")
        return self.value


def test_requests_panel_is_cached_so_a_page_poll_is_not_a_gateway_poll(monkeypatch):
    monkeypatch.setattr(worker_activity, "_requests_cache", {"at": 0.0, "value": None})
    source = _Supervision({"available": True, "open": [{"request_id": "rq_1"}]})
    first = worker_activity._requests(now=1000.0, source=source)
    worker_activity._requests(now=1010.0, source=source)
    assert source.calls == 1 and first["open"][0]["request_id"] == "rq_1" and first["fetched_at"] == 1000.0
    worker_activity._requests(now=1000.0 + worker_activity.REQUESTS_CACHE_SECONDS, source=source)
    assert source.calls == 2


def test_requests_panel_failure_is_reported_never_raised(monkeypatch):
    monkeypatch.setattr(worker_activity, "_requests_cache", {"at": 0.0, "value": None})
    out = worker_activity._requests(now=5.0, source=_Supervision(boom=True))
    assert out["available"] is False and "RuntimeError" in out["reason"]
