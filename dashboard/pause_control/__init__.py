"""Pause/resume *control requests* against the StarTrekBridge task ledger.

This package never claims to pause or resume a task itself. The task ledger,
the worker that executes tasks (`adw_bridge_worker.py` in `agent_blocks`,
outside this repository) and the lease/checkpoint logic that would make a
pause safe all live outside this workspace -- see
`docs/bridge-pause-resume.md` for the exact blocker and the wiring an
on-machine agent with `agent_blocks` access still needs to do.

What this package *does* own, durably: recording EG's/ChatGPT's intent to
pause, resume or prioritize one task (by the task_id the ledger already
uses), a fail-closed check for whether a task is even known to support a
safe pause, idempotent de-duplication of repeated requests, and an audit
trail of every pause_requested/paused/resume_requested/resumed/failed
transition. `PauseControlService` is the one entry point; concretes are
named only in `composition.py`.
"""
