"""Regression coverage for exact Recent Report callback correlation."""

import json

import server
from intake.recent_intake_contracts import RecentIntakeEventIdentity
from intake.recent_intake_routing import ExactRecentIntakeEventRouter


def _pointer_environment(tmp_path, monkeypatch):
    pointer = tmp_path / "recent_report.json"
    pointer.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(server, "RECENT_REPORT_POINTER_FILE", str(pointer))
    monkeypatch.setattr(server, "_resolve_duplicate_expense_ids", lambda *_args: [])
    return pointer


def test_uncorrelated_callback_cannot_mutate_active_scanner_intake(
    tmp_path, monkeypatch
):
    pointer = _pointer_environment(tmp_path, monkeypatch)
    server.record_recent_intake(
        "/staged/window_scan.jpg",
        "Window Scanner",
        conversation_id="conv-window",
        dispatched_at=100.0,
    )

    server.record_stored_expense(
        {
            "kind": "statement",
            "expense_ids": [2128],
            "duplicate_expense_ids": [2128],
            "parsed": 1,
            "stored": 0,
        }
    )

    data = json.loads(pointer.read_text(encoding="utf-8"))
    assert data["intake"]["expense_ids"] == []
    assert data["intake"]["duplicate_expense_ids"] == []
    assert data["intake"]["parsed"] is None
    assert data["scanner_intakes"]["Window Scanner"]["expense_ids"] == []
    assert server.get_stored_expense_events(0)[-1]["expense_ids"] == [2128]


def test_identity_contract_accepts_legacy_receipt_url_but_not_empty_payload():
    assert RecentIntakeEventIdentity.from_mapping({"parsed": 1}) is None
    identity = RecentIntakeEventIdentity.from_mapping(
        {"receipt_url": " /staged/window.jpg "}
    )
    assert identity is not None
    assert identity.document_path == "/staged/window.jpg"


def test_router_uses_path_to_disambiguate_nearby_dispatches():
    identity = RecentIntakeEventIdentity.from_mapping(
        {"document_path": "/staged/freezer.jpg", "dispatched_at": 101}
    )
    assert identity is not None
    window = {"image_path": "/staged/window.jpg", "dispatched_at": 100.0}
    freezer = {"image_path": "/staged/freezer.jpg", "dispatched_at": 101.0}

    targets = ExactRecentIntakeEventRouter().select_targets(
        identity, [window, freezer]
    )

    assert targets == [freezer]


def test_router_never_falls_back_from_wrong_conversation_to_latest_record():
    identity = RecentIntakeEventIdentity.from_mapping(
        {
            "document_path": "/staged/reused.jpg",
            "conversation_id": "conv-old",
            "dispatched_at": 100,
        }
    )
    assert identity is not None
    current = {
        "image_path": "/staged/reused.jpg",
        "conversation_id": "conv-current",
        "dispatched_at": 200.0,
    }

    assert ExactRecentIntakeEventRouter().select_targets(identity, [current]) == []
