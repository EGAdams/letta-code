from __future__ import annotations

import subprocess

from ssh_gateway import ConfiguredIdentityStrategy, OpenSshGateway, SshTarget


class FakeRunner:
    def __init__(self, result):
        self.result = result
        self.commands = []

    def run(self, command, *, timeout):
        self.commands.append((list(command), timeout))
        return self.result


def test_gateway_uses_first_existing_configured_identity(tmp_path):
    identity = tmp_path / 'id_ed25519'
    identity.write_text('test key')
    runner = FakeRunner(subprocess.CompletedProcess(
        ['ssh'], 0, 'CONNECTED\nDESKTOP-SHDBATI\n', ''))
    gateway = OpenSshGateway(
        runner=runner,
        credentials=ConfiguredIdentityStrategy(),
    )

    result = gateway.test_connection(
        SshTarget('NewUser', '100.118.122.75', ('~/.missing', str(identity))),
        timeout=8,
    )

    assert result == {'ok': True, 'text': 'CONNECTED — DESKTOP-SHDBATI'}
    assert runner.commands == [(
        [
            'ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=accept-new', '-o', 'IdentitiesOnly=yes',
            '-i', str(identity), 'NewUser@100.118.122.75',
            'echo CONNECTED && hostname',
        ],
        18,
    )]


def test_gateway_preserves_permission_denied_text():
    runner = FakeRunner(subprocess.CompletedProcess(
        ['ssh'], 255, '', 'NewUser@100.118.122.75: Permission denied (publickey).\n'))

    result = OpenSshGateway(runner=runner).test_connection(
        SshTarget('NewUser', '100.118.122.75'), timeout=8)

    assert result == {
        'ok': False,
        'text': 'NewUser@100.118.122.75: Permission denied (publickey).',
    }
