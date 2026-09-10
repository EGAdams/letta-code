"""Strict data contracts for routing Recent Report intake callbacks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contracts import StrictModel


class RecentIntakeEventIdentity(StrictModel):
    """The explicit evidence that ties one callback to one intake dispatch."""

    document_path: str = ""
    conversation_id: str = ""
    dispatched_at: float | None = None

    @classmethod
    def from_mapping(
        cls, payload: Mapping[str, Any]
    ) -> RecentIntakeEventIdentity | None:
        document_path = str(
            payload.get("document_path") or payload.get("receipt_url") or ""
        ).strip()
        conversation_id = str(payload.get("conversation_id") or "").strip()
        try:
            dispatched_at = float(payload.get("dispatched_at") or 0)
        except (TypeError, ValueError):
            dispatched_at = 0.0
        if dispatched_at <= 0:
            dispatched_at = None
        if not document_path and not conversation_id and dispatched_at is None:
            return None
        return cls(
            document_path=document_path,
            conversation_id=conversation_id,
            dispatched_at=dispatched_at,
        )

