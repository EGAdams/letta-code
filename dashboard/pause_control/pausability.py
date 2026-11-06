"""ITaskPausability: fail-closed, because nothing in this workspace can prove a
task has a cooperative checkpoint to pause at.

Real pausability -- "this task's worker ADW checks a pause flag between
phases and extends its lease instead of claiming the next step" -- is a
property of code that lives in `agent_blocks`, outside this repository (see
`docs/bridge-pause-resume.md`). Until that owner publishes which task kinds
are safe, every task_id this process has not been explicitly told about
answers `None` ("unknown"), and `PauseControlService` refuses to turn an
unknown task into a pause request.
"""

from __future__ import annotations

from typing import Optional


class ConfiguredTaskPausability:
    def __init__(self, pausable: frozenset[str] = frozenset(), not_pausable: frozenset[str] = frozenset()):
        if pausable & not_pausable:
            raise ValueError('a task_id cannot be both pausable and not_pausable')
        self._pausable, self._not_pausable = pausable, not_pausable

    def can_pause(self, task_id: str) -> Optional[bool]:
        if task_id in self._not_pausable:
            return False
        if task_id in self._pausable:
            return True
        return None
