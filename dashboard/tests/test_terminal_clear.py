import json

from monitoring import terminal_clear


def test_clear_increments_shared_epoch_and_does_not_touch_other_files(tmp_path, monkeypatch):
    state = tmp_path / "terminal-clear.json"
    ledger = tmp_path / "worker-activity.json"
    ledger.write_text(json.dumps([{"id": "old"}]))
    monkeypatch.setattr(terminal_clear, "DEFAULT_STATE", state)

    assert terminal_clear.epoch() == 0
    assert terminal_clear.clear()["terminal_clear_epoch"] == 1
    assert terminal_clear.clear()["terminal_clear_epoch"] == 2
    assert json.loads(ledger.read_text()) == [{"id": "old"}]
