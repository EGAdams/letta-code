"""Both bridge workers observed one by one: a crash of either shows, an uninstalled lane is not a failure."""
import json

from monitoring import agent_bridge_poll, worker_lanes

NOW = 1_800_000_000.0


def _page(active="active", pid=4242, loaded="loaded", state=None):
    service = {"active": active, "sub": "running", "enabled": "enabled", "pid": pid, "started_at": NOW - 600,
               "loaded": loaded}
    return {"polling": "active", "reason": "polling", "service": service, "state": state}


def _fresh(pid=4242):
    return {"phase": "waiting", "pid": pid, "checked_at": NOW - 5, "next_check_at": NOW + 25, "checks": 7}


class Probe:
    """Stands in for /proc: the PID is a bridge worker unless it is 0."""

    def inspect(self, pid):
        from monitoring.worker_supervisor import ProcessObservation
        return ProcessObservation(pid, bool(pid), "python adw_bridge_worker.py --watch", "")


def test_two_lanes_are_configured_with_their_own_unit_and_files():
    general, express = worker_lanes.LANES
    assert (general.name, express.name) == ("general", "express")
    assert general.service == "agent-bridge-worker.service"
    assert express.service == "agent-bridge-worker-express.service"
    assert general.state_path != express.state_path and general.health_path != express.health_path


def test_each_lane_is_read_through_its_own_unit_and_state_file(monkeypatch):
    asked = []

    def poll(service, state_path):
        asked.append((service, state_path.name))
        return _page(state=_fresh())

    monkeypatch.setattr("monitoring.worker_supervisor.ProcWorkerProbe", Probe)
    reports = worker_lanes.lane_reports(now=NOW, poll=poll)
    assert asked == [("agent-bridge-worker.service", "poll_state.json"),
                     ("agent-bridge-worker-express.service", "poll_state_express.json")]
    assert [r["lane"] for r in reports] == ["general", "express"]
    assert all(r["installed"] and r["healthy"] for r in reports)


def test_a_crashed_express_worker_is_unhealthy_while_general_stays_healthy(monkeypatch):
    monkeypatch.setattr("monitoring.worker_supervisor.ProcWorkerProbe", Probe)

    def poll(service, state_path):
        if "express" in service:
            return _page(active="failed", pid=0, state=_fresh(0))
        return _page(state=_fresh())

    general, express = worker_lanes.lane_reports(now=NOW, poll=poll)
    assert general["healthy"] is True
    assert express["installed"] is True and express["healthy"] is False
    assert express["status"] == "offline"


def test_a_lane_that_was_never_installed_is_not_a_failure():
    def poll(service, state_path):
        return _page(active="inactive", pid=0, loaded="not-found") if "express" in service else _page(state=_fresh())

    express = worker_lanes.lane_reports(now=NOW, poll=poll)[1]
    assert express["installed"] is False and express["healthy"] is None
    assert express["status"] == "not installed"


def test_queue_age_does_not_make_a_lane_unhealthy(monkeypatch):
    """A coding write waiting behind another is expected while express is idle; that is judged on the queue, not the lane."""
    monkeypatch.setattr("monitoring.worker_supervisor.ProcWorkerProbe", Probe)
    general, express = worker_lanes.lane_reports(now=NOW, poll=lambda s, p: _page(state=_fresh()))
    assert general["diagnostic"]["queue"]["stagnant"] is False and express["healthy"] is True


def test_supervisor_health_file_is_attached_per_lane(tmp_path, monkeypatch):
    health = tmp_path / "worker_health_express.json"
    health.write_text(json.dumps({"checked_at": "t", "status": "healthy", "action": "none", "secret": "x"}))
    lane = worker_lanes.LANES[1].model_copy(update={"health_path": health})
    monkeypatch.setattr("monitoring.worker_supervisor.ProcWorkerProbe", Probe)
    report = worker_lanes.lane_report(lane, NOW, lambda s, p: _page(state=_fresh()))
    assert report["supervisor"]["status"] == "healthy" and "secret" not in report["supervisor"]


def test_service_state_reads_load_state_from_systemd_output():
    assert agent_bridge_poll.parse_show("ActiveState=inactive\nLoadState=not-found\n").loaded == "not-found"
