"""Fail-closed routing strategy for Recent Report callbacks."""

from __future__ import annotations

from collections.abc import Sequence

from intake.recent_intake_contracts import RecentIntakeEventIdentity
from intake.recent_intake_ports import IRecentIntakeEventRouter, IntakeRecord


class ExactRecentIntakeEventRouter(IRecentIntakeEventRouter):
    """Match dispatch identity first, with document path as a tie-breaker."""

    dispatch_tolerance_seconds = 2.0

    def select_targets(
        self,
        identity: RecentIntakeEventIdentity,
        candidates: Sequence[IntakeRecord],
    ) -> list[IntakeRecord]:
        if identity.conversation_id or identity.dispatched_at is not None:
            targets = [
                intake
                for intake in candidates
                if self._dispatch_matches(identity, intake)
            ]
            if identity.document_path and len(targets) > 1:
                named = [
                    intake
                    for intake in targets
                    if intake.get("image_path") == identity.document_path
                ]
                if named:
                    return named
            return targets

        return [
            intake
            for intake in candidates
            if intake.get("image_path") == identity.document_path
        ]

    def _dispatch_matches(
        self, identity: RecentIntakeEventIdentity, intake: IntakeRecord
    ) -> bool:
        if (
            identity.conversation_id
            and intake.get("conversation_id") != identity.conversation_id
        ):
            return False
        if identity.dispatched_at is None:
            return True
        try:
            candidate_time = float(intake.get("dispatched_at") or 0)
        except (TypeError, ValueError):
            return False
        return (
            abs(candidate_time - identity.dispatched_at)
            < self.dispatch_tolerance_seconds
        )

