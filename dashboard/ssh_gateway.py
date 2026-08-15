"""Ports and adapters for dashboard SSH connection probes."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
import subprocess
from typing import Protocol, Sequence

@dataclass(frozen=True)
class SshTarget:
    user: str
    host: str
    identity_files: tuple[str, ...] = ()

class ICommandRunner(Protocol):
    def run(self, command: Sequence[str], *, timeout: float) -> subprocess.CompletedProcess[str]: ...

class ICredentialStrategy(ABC):
    @abstractmethod
    def options(self, target: SshTarget) -> tuple[str, ...]: ...

class ConfiguredIdentityStrategy(ICredentialStrategy):
    def options(self, target: SshTarget) -> tuple[str, ...]:
        for configured in target.identity_files:
            identity = os.path.expanduser(configured)
            if identity and os.path.isfile(identity):
                return ('-o', 'IdentitiesOnly=yes', '-i', identity)
        return ()

class ISshGateway(ABC):
    @abstractmethod
    def test_connection(self, target: SshTarget, *, timeout: float) -> dict[str, object]: ...

class SubprocessCommandRunner:
    def run(self, command: Sequence[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout)

class OpenSshGateway(ISshGateway):
    def __init__(self, *, runner: ICommandRunner | None = None, credentials: ICredentialStrategy | None = None) -> None:
        self._runner = runner or SubprocessCommandRunner()
        self._credentials = credentials or ConfiguredIdentityStrategy()

    def test_connection(self, target: SshTarget, *, timeout: float) -> dict[str, object]:
        destination = f'{target.user}@{target.host}'
        command = ['ssh', '-o', f'ConnectTimeout={timeout}', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new', *self._credentials.options(target), destination, 'echo CONNECTED && hostname']
        try:
            result = self._runner.run(command, timeout=timeout + 10)
        except subprocess.TimeoutExpired:
            return {'ok': False, 'text': f'ssh to {destination} timed out after {timeout}s'}
        except Exception as exc:
            return {'ok': False, 'text': f'ssh to {destination} failed: {exc}'}
        output = (result.stdout or '').strip().splitlines()
        if result.returncode == 0 and output and output[0].strip() == 'CONNECTED':
            hostname = output[1].strip() if len(output) > 1 else '?'
            return {'ok': True, 'text': f'CONNECTED — {hostname}'}
        errors = (result.stderr or result.stdout or '').strip().splitlines()
        return {'ok': False, 'text': errors[-1][:160] if errors else f'ssh exited {result.returncode}'}
