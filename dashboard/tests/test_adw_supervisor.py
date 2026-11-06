import json

from monitoring import adw_supervisor as sup


THRESHOLDS = sup.Thresholds(
    warn_seconds=120, recommend_seconds=300, diagnose_seconds=600, incident_seconds=1800,
)


def test_tier_for_age_matches_the_configured_default_boundaries():
    assert sup.tier_for_age(0, THRESHOLDS) == "ok"
    assert sup.tier_for_age(119, THRESHOLDS) == "ok"
    assert sup.tier_for_age(120, THRESHOLDS) == "warn"
    assert sup.tier_for_age(300, THRESHOLDS) == "recommend"
    assert sup.tier_for_age(600, THRESHOLDS) == "diagnose"
    assert sup.tier_for_age(1800, THRESHOLDS) == "incident"


def test_thresholds_from_env_are_configurable(monkeypatch):
    monkeypatch.setenv("ADW_SUPERVISOR_WARN_SECONDS", "5")
    monkeypatch.setenv("ADW_SUPERVISOR_RECOMMEND_SECONDS", "10")
    monkeypatch.setenv("ADW_SUPERVISOR_DIAGNOSE_SECONDS", "15")
    monkeypatch.setenv("ADW_SUPERVISOR_INCIDENT_SECONDS", "20")

    thresholds = sup.Thresholds.from_env()

    assert thresholds == sup.Thresholds(5, 10, 15, 20)


def test_queue_age_prefers_the_worker_supplied_field():
    task = {"queue_age": 42, "queued_at": 0}
    assert sup._queue_age(task, now=1000) == 42


def test_queue_age_falls_back_to_queued_at():
    task = {"queued_at": 100}
    assert sup._queue_age(task, now=142) == 42


def test_queue_age_is_none_when_neither_field_is_present():
    assert sup._queue_age({}, now=1000) is None


def test_running_task_needs_progress_telemetry_not_its_past_queue_age():
    task = {"id": "t1", "status": "running", "queue_age": 99999, "attempts": 1}

    state = sup.evaluate_task(task, sup.TaskEscalationState(), THRESHOLDS, now=0)

    assert state.tier == "ok"
    assert state.events == []
    assert state.observation_error


def test_queued_task_escalates_through_fake_clock_time(monkeypatch):
    monkeypatch.setattr(sup, "second_opinion_models", lambda: ["claude-sonnet"])
    task = {"id": "t1", "status": "queued", "attempts": 0}
    state = sup.TaskEscalationState()

    for age, expected_tier in ((0, "ok"), (121, "warn"), (301, "recommend"), (601, "diagnose"), (1801, "incident")):
        task["queue_age"] = age
        state = sup.evaluate_task(task, state, THRESHOLDS, now=age, candidates=("claude-sonnet",))
        assert state.tier == expected_tier

    tiers_recorded = [event["tier"] for event in state.events]
    assert tiers_recorded == ["warn", "recommend", "diagnose", "incident"]
    diagnose_event = next(e for e in state.events if e["tier"] == "diagnose")
    assert diagnose_event["second_opinion_models"] == ["claude-sonnet"]


def test_escalation_is_idempotent_on_repeated_identical_cycles():
    task = {"id": "t1", "status": "queued", "attempts": 0, "queue_age": 150}
    state = sup.evaluate_task(task, sup.TaskEscalationState(), THRESHOLDS, now=0)
    assert len(state.events) == 1

    state_again = sup.evaluate_task(task, state, THRESHOLDS, now=1)

    assert state_again.tier == "warn"
    assert len(state_again.events) == 1  # no duplicate "entered warn" event


def test_two_no_progress_cycles_recommend_switching_tactic():
    task = {"id": "t1", "status": "queued", "attempts": 0, "queue_age": 150}
    state = sup.TaskEscalationState()
    state = sup.evaluate_task(task, state, THRESHOLDS, now=0)   # enters warn
    state = sup.evaluate_task(task, state, THRESHOLDS, now=1)   # cycle 1, no progress
    assert not any("switch tactic" in e["message"] for e in state.events)
    state = sup.evaluate_task(task, state, THRESHOLDS, now=2)   # cycle 2, no progress

    assert any("switch tactic" in e["message"] for e in state.events)


def test_progress_resets_the_no_progress_counter():
    task = {"id": "t1", "status": "queued", "attempts": 0, "queue_age": 150}
    state = sup.evaluate_task(task, sup.TaskEscalationState(), THRESHOLDS, now=0)
    state = sup.evaluate_task(task, state, THRESHOLDS, now=1)
    task = {**task, "attempts": 1}  # progress: a retry happened
    state = sup.evaluate_task(task, state, THRESHOLDS, now=2)

    assert state.no_progress_cycles == 0


def test_task_leaving_the_queue_resets_its_state():
    task = {"id": "t1", "status": "queued", "attempts": 0, "queue_age": 400}
    state = sup.evaluate_task(task, sup.TaskEscalationState(), THRESHOLDS, now=0)
    assert state.tier == "recommend"

    task = {"id": "t1", "status": "succeeded", "attempts": 1}
    state = sup.evaluate_task(task, state, THRESHOLDS, now=1)

    assert state.tier == "ok"
    assert state.events == []


def test_events_are_capped_at_max_events():
    state = sup.TaskEscalationState(events=[{"at": i} for i in range(sup.MAX_EVENTS + 10)])

    assert len(state.to_dict()["events"]) == sup.MAX_EVENTS


def test_read_ledger_reports_missing_file_honestly(tmp_path):
    tasks, error, updated_at = sup.read_ledger(tmp_path / "absent.json")

    assert tasks is None
    assert "not present" in error
    assert updated_at is None


def test_read_ledger_rejects_an_invalid_shape(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps({"not": "a list"}))

    tasks, error, updated_at = sup.read_ledger(path)

    assert tasks is None
    assert "invalid shape" in error
    assert updated_at is not None


def test_read_ledger_returns_rows_for_a_valid_snapshot(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps([{"id": "t1", "status": "queued"}]))

    tasks, error, updated_at = sup.read_ledger(path)

    assert tasks[0]["id"] == "t1" and tasks[0]["status"] == "queued"
    assert error is None
    assert updated_at is not None


def test_run_cycle_is_honest_when_ledger_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(sup, "_worker_diagnostic", lambda tasks, now: None)
    monkeypatch.setattr(sup.model_registry, "registry", lambda: [])
    state_path = tmp_path / "state.json"

    snapshot = sup.run_cycle(
        ledger_path=tmp_path / "missing.json", state_path=state_path,
        thresholds=THRESHOLDS, now=1000.0,
    )

    assert snapshot["ok"] is False
    assert snapshot["source"] == "unavailable"
    assert snapshot["tasks"] == {}
    assert snapshot["alerts"] == []
    assert json.loads(state_path.read_text()) == snapshot


def test_run_cycle_writes_an_atomic_snapshot_with_alerts(tmp_path, monkeypatch):
    monkeypatch.setattr(sup, "_worker_diagnostic", lambda tasks, now: {"status": "healthy"})
    monkeypatch.setattr(sup.model_registry, "registry", lambda: [])
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps([{"id": "t1", "status": "queued", "attempts": 0, "queue_age": 400}]))
    state_path = tmp_path / "state.json"

    snapshot = sup.run_cycle(
        ledger_path=ledger_path, state_path=state_path, thresholds=THRESHOLDS, now=ledger_path.stat().st_mtime,
    )

    assert snapshot["ok"] is True
    assert snapshot["tasks"]["t1"]["tier"] == "recommend"
    assert snapshot["alerts"][0]["task_id"] == "t1"
    assert not (tmp_path / "state.json.tmp").exists()


def test_run_cycle_carries_escalation_state_across_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(sup, "_worker_diagnostic", lambda tasks, now: None)
    monkeypatch.setattr(sup.model_registry, "registry", lambda: [])
    ledger_path = tmp_path / "ledger.json"
    state_path = tmp_path / "state.json"
    ledger_path.write_text(json.dumps([{"id": "t1", "status": "queued", "attempts": 0, "queue_age": 150}]))
    first = sup.run_cycle(ledger_path=ledger_path, state_path=state_path, thresholds=THRESHOLDS, now=ledger_path.stat().st_mtime)
    assert first["tasks"]["t1"]["tier"] == "warn"

    ledger_path.write_text(json.dumps([{"id": "t1", "status": "queued", "attempts": 0, "queue_age": 1900}]))
    second = sup.run_cycle(ledger_path=ledger_path, state_path=state_path, thresholds=THRESHOLDS, now=ledger_path.stat().st_mtime + 1)

    assert second["tasks"]["t1"]["tier"] == "incident"
    assert second["tasks"]["t1"]["highest_tier"] == "incident"


def test_real_worker_iso_timestamp_and_formatted_duration_escalate():
    task = {"id": "real", "status": "queued", "attempts": 0,
            "queue_age": "10m 1s", "queued_at": "2026-11-06T13:00:00+00:00"}
    state = sup.evaluate_task(task, sup.TaskEscalationState(), THRESHOLDS, now=1793970601)
    assert state.tier == "diagnose"


def test_stale_ledger_never_reports_healthy(tmp_path, monkeypatch):
    import os
    monkeypatch.setattr(sup, "_worker_diagnostic", lambda tasks, now: None)
    monkeypatch.setattr(sup.model_registry, "registry", lambda: [])
    ledger = tmp_path / "ledger.json"
    ledger.write_text('[]')
    os.utime(ledger, (100, 100))
    result = sup.run_cycle(ledger_path=ledger, state_path=tmp_path / "state.json",
                           thresholds=THRESHOLDS, now=1000)
    assert result["ok"] is False
    assert result["ledger_stale"] is True


def test_running_task_without_recent_progress_escalates():
    task = {"id": "run", "status": "running", "attempts": 1,
            "last_update": "2026-11-06T13:00:00+00:00"}
    state = sup.evaluate_task(task, sup.TaskEscalationState(), THRESHOLDS, now=1793970601)
    assert state.tier == "diagnose"


def test_unknown_age_is_explicit_and_does_not_erase_prior_escalation():
    prior = sup.TaskEscalationState(tier="recommend", highest_tier="recommend")
    state = sup.evaluate_task({"id": "x", "status": "queued"}, prior, THRESHOLDS, now=1000)
    assert state.tier == "recommend"
    assert state.observation_error
