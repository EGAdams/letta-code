"""Interfaces for Recent Report callback routing behavior."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import MutableMapping, Sequence
from typing import Any

from intake.recent_intake_contracts import RecentIntakeEventIdentity

IntakeRecord = MutableMapping[str, Any]


class IRecentIntakeEventRouter(ABC):
    @abstractmethod
    def select_targets(
        self,
        identity: RecentIntakeEventIdentity,
        candidates: Sequence[IntakeRecord],
    ) -> list[IntakeRecord]:
        """Return only intake records proven to belong to the callback."""

