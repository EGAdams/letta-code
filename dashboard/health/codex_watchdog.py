"""Policy and orchestration for the local Codex CLI quota watchdog.

`evaluate()` is the whole policy and is pure -- no I/O, no clock reads beyond
the `now` it is given -- so the incident scenario (multiple concurrent
autonomous sessions, one at 97% quota, one stopped in place) is a table of
inputs and expected decisions, not a live process to reproduce. `CodexWatchdog`
is the thin orchestration shell that feeds it real process/quota readings and
applies the resulting decisions.
"""

from __future__ import annotations

import time
from typing import Callable, Dict, List, Tuple

from health.codex_watchdog_contracts import (
    ICodexProcessController,
    ICodexProcessInspector,
    ICodexSessionReader,
    IWatchdogActionStore,
    KILL_PRIMARY_PERCENT,
    MAX_CONCURRENT_AUTONOMOUS,
    POLL_INTERVAL_SECONDS,
    STOPPED_REAP_SECONDS,
    WARN_PRIMARY_PERCENT,
    CodexProcessGroup,
    CodexUsageSample,
    WatchdogAction,
    WatchdogDecision,
)


def evaluate(
    groups: List[CodexProcessGroup],
    usage_by_session: Dict[str, CodexUsageSample],
    stopped_since: Dict[int, float],
    now: float,
    *,
    kill_percent: float = KILL_PRIMARY_PERCENT,
    warn_percent: float = WARN_PRIMARY_PERCENT,
    max_concurrent: int = MAX_CONCURRENT_AUTONOMOUS,
    stopped_reap_seconds: float = STOPPED_REAP_SECONDS,
) -> Tuple[List[WatchdogDecision], Dict[int, float]]:
    """What to do about each running autonomous Codex session, right now.

    Only autonomous sessions (`AUTONOMOUS_FLAG` in the command line) are ever
    candidates for termination -- a session a person is watching and
    approving prompts in is never killed by this policy, no matter its quota.

    `stopped_since` is the one piece of state this needs across polls (how
    long a group has been sitting in `T`), threaded through explicitly as an
    argument and returned updated, rather than kept as hidden instance state,
    so the whole policy stays a pure function of its inputs.
    """
    autonomous = [g for g in groups if g.autonomous]
    decisions: List[WatchdogDecision] = []
    next_stopped_since = dict(stopped_since)

    for group in autonomous:
        if group.stopped:
            since = next_stopped_since.setdefault(group.pgid, now)
            if now - since >= stopped_reap_seconds:
                decisions.append(WatchdogDecision(
                    group=group,
                    action='terminate_stopped',
                    reason=(f'stopped for {now - since:.0f}s '
                            f'(limit {stopped_reap_seconds:.0f}s)'),
                ))
        else:
            next_stopped_since.pop(group.pgid, None)

    live_pgids = {g.pgid for g in groups}
    next_stopped_since = {pgid: ts for pgid, ts in next_stopped_since.items()
                           if pgid in live_pgids}

    killed_pgids = {d.group.pgid for d in decisions}
    survivors = [g for g in autonomous if g.pgid not in killed_pgids]

    for group in survivors:
        usage = (usage_by_session.get(group.session_path)
                  if group.session_path else None)
        if usage is None:
            continue
        if usage.primary_used_percent >= kill_percent:
            decisions.append(WatchdogDecision(
                group=group,
                action='terminate_quota',
                reason=(f'{usage.primary_used_percent:.0f}% of 5h Codex '
                        f'quota used (limit {kill_percent:.0f}%)'),
                used_percent=usage.primary_used_percent,
            ))
        elif usage.primary_used_percent >= warn_percent:
            decisions.append(WatchdogDecision(
                group=group,
                action='warn_quota',
                reason=(f'{usage.primary_used_percent:.0f}% of 5h Codex '
                        f'quota used (warn at {warn_percent:.0f}%)'),
                used_percent=usage.primary_used_percent,
            ))

    killed_pgids = {d.group.pgid for d in decisions
                     if d.action.startswith('terminate')}
    survivors = [g for g in survivors if g.pgid not in killed_pgids]
    # Trainer-dispatched sessions (see TRAINER_CWD_MARKER) never count toward
    # or lose the concurrency slot -- Trainer already bounds and retries its
    # own Codex calls, so it is not the unattended-session risk this cap
    # exists for, and must not compete with a human's session for it.
    concurrency_candidates = [g for g in survivors if not g.supervised]
    if len(concurrency_candidates) > max_concurrent:
        oldest_first = sorted(concurrency_candidates, key=lambda g: -g.elapsed_seconds)
        for group in oldest_first[max_concurrent:]:
            decisions.append(WatchdogDecision(
                group=group,
                action='terminate_concurrency',
                reason=(f'{len(concurrency_candidates)} concurrent autonomous Codex '
                        f'sessions running (limit {max_concurrent})'),
            ))

    return decisions, next_stopped_since


class CodexWatchdog:
    """Wires the ports together and runs `evaluate()` on an interval."""

    def __init__(
        self,
        *,
        inspector: ICodexProcessInspector,
        reader: ICodexSessionReader,
        controller: ICodexProcessController,
        store: IWatchdogActionStore,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        log: Callable[[str], None] = lambda _line: None,
        kill_percent: float = KILL_PRIMARY_PERCENT,
        warn_percent: float = WARN_PRIMARY_PERCENT,
        max_concurrent: int = MAX_CONCURRENT_AUTONOMOUS,
        stopped_reap_seconds: float = STOPPED_REAP_SECONDS,
        poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
        kill_grace_seconds: float = 3.0,
    ) -> None:
        self._inspector = inspector
        self._reader = reader
        self._controller = controller
        self._store = store
        self._clock = clock
        self._sleeper = sleeper
        self._log = log
        self._kill_percent = kill_percent
        self._warn_percent = warn_percent
        self._max_concurrent = max_concurrent
        self._stopped_reap_seconds = stopped_reap_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._kill_grace_seconds = kill_grace_seconds
        self._stopped_since: Dict[int, float] = {}
        self._warned_pgids: set = set()

    def poll_once(self) -> List[WatchdogDecision]:
        groups = self._inspector.running_groups()
        usage_by_session: Dict[str, CodexUsageSample] = {}
        for group in groups:
            if not group.session_path or group.session_path in usage_by_session:
                continue
            sample = self._reader.usage_for(group.session_path)
            if sample is not None:
                usage_by_session[group.session_path] = sample

        decisions, self._stopped_since = evaluate(
            groups, usage_by_session, self._stopped_since, self._clock(),
            kill_percent=self._kill_percent,
            warn_percent=self._warn_percent,
            max_concurrent=self._max_concurrent,
            stopped_reap_seconds=self._stopped_reap_seconds,
        )
        for decision in decisions:
            self._apply(decision)
        return decisions

    def _apply(self, decision: WatchdogDecision) -> None:
        pgid = decision.group.pgid
        if decision.action == 'warn_quota':
            if pgid in self._warned_pgids:
                return
            self._warned_pgids.add(pgid)
            self._log(f'WARN pgid={pgid}: {decision.reason}')
        else:
            self._log(f'KILL pgid={pgid} ({decision.action}): {decision.reason}')
            self._controller.terminate(pgid)
            self._sleeper(self._kill_grace_seconds)
            self._controller.force_kill(pgid)
            self._warned_pgids.discard(pgid)
        self._store.record(WatchdogAction(
            timestamp=self._clock(),
            action=decision.action,
            pgid=pgid,
            cmd=decision.group.cmd,
            reason=decision.reason,
            used_percent=decision.used_percent,
        ))

    def run_forever(self) -> None:
        self._log(
            f'codex watchdog running: kill>={self._kill_percent:.0f}% '
            f'warn>={self._warn_percent:.0f}% '
            f'max_concurrent={self._max_concurrent} '
            f'stopped_reap={self._stopped_reap_seconds:.0f}s '
            f'poll={self._poll_interval_seconds:.0f}s')
        while True:
            try:
                self.poll_once()
            except Exception as exc:  # noqa: BLE001 - a watchdog must not die
                self._log(f'poll error: {exc!r}')
            self._sleeper(self._poll_interval_seconds)
