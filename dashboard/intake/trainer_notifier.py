"""Concrete detached-process adapter for the Trainer notification port."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Mapping
from typing import Any

from intake.trainer_contracts import ITrainerNotifier, TrainerLaunchRequest


def build_trainer_command(
    runner: str,
    script: str,
    scan_path: str,
    scanner_name: str,
    facade_result: Mapping[str, Any] | None = None,
    dispatched_at: float | None = None,
    conversation_id: str | None = None,
) -> list[str]:
    command = [
        runner,
        script,
        '--scan-path',
        scan_path,
        '--scanner',
        scanner_name,
        '--facade',
        json.dumps(dict(facade_result or {}), default=str),
    ]
    if dispatched_at is not None:
        command += ['--dispatched-at', str(int(dispatched_at))]
    if conversation_id:
        command += ['--conversation-id', conversation_id]
    return command


class NullTrainerNotifier(ITrainerNotifier):
    def notify(self, request: TrainerLaunchRequest) -> bool:
        return False


class DetachedTrainerNotifier(ITrainerNotifier):
    def __init__(self, runner: str, script: str):
        self._runner = runner
        self._script = script

    def notify(self, request: TrainerLaunchRequest) -> bool:
        if not os.path.isfile(self._script):
            print(f'[scan→trainer] Trainer script missing: {self._script}')
            return False
        scanner_slug = (
            re.sub(r'[^A-Za-z0-9]+', '_', request.scanner_name).strip('_')
            or 'scanner'
        )
        conversation_slug = re.sub(
            r'[^A-Za-z0-9]+', '', request.conversation_id
        )[-12:]
        dispatch_second = int(request.dispatched_at)
        log_path = (
            f'/tmp/mazda_trainer_{dispatch_second}_{scanner_slug}_'
            f'{conversation_slug}.log'
        )
        command = build_trainer_command(
            self._runner,
            self._script,
            request.scan_path,
            request.scanner_name,
            request.facade_result,
            request.dispatched_at,
            request.conversation_id,
        )
        unit_name = (
            f'mazda-trainer-{dispatch_second}-{scanner_slug}-{conversation_slug}'
        )
        command = [
            'systemd-run',
            '--user',
            '--scope',
            '--collect',
            '--quiet',
            f'--unit={unit_name}',
            *command,
        ]
        environment = dict(os.environ)
        environment['PATH'] = ':'.join([
            os.path.expanduser('~/.bun/bin'),
            os.path.expanduser('~/.local/bin'),
            os.path.expanduser('~/.npm-global/bin'),
            environment.get('PATH', '/usr/bin:/bin'),
        ])
        try:
            with open(log_path, 'ab') as log:
                subprocess.Popen(
                    command,
                    stdout=log,
                    stderr=log,
                    env=environment,
                    cwd=os.path.dirname(self._script),
                    start_new_session=True,
                )
        except Exception as exc:
            print(f'[scan→trainer] Failed to launch trainer: {exc}')
            return False
        print(
            f'[scan→trainer] Trainer summoned for {request.scanner_name}; '
            f'log: {log_path}'
        )
        return True
