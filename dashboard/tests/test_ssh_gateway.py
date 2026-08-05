from __future__ import annotations
import subprocess
from ssh_gateway import ConfiguredIdentityStrategy, OpenSshGateway, SshTarget

class FakeRunner:
    def __init__(self, result): self.result, self.commands = result, []
    def run(self, command, *, timeout): self.commands.append((list(command), timeout)); return self.result

def test_gateway_uses_first_existing_configured_identity(tmp_path):
    identity = tmp_path / 'id_ed25519'; identity.write_text('test key')
    runner = FakeRunner(subprocess.CompletedProcess(['ssh'], 0, 'CONNECTED\nDESKTOP-SHDBATI\n', ''))
    result = OpenSshGateway(runner=runner, credentials=ConfiguredIdentityStrategy()).test_connection(SshTarget('NewUser', '100.69.80.89', ('~/.missing', str(identity))), timeout=8)
    assert result == {'ok': True, 'text': 'CONNECTED — DESKTOP-SHDBATI'}
    assert runner.commands[0][0][-6:] == ['-o', 'IdentitiesOnly=yes', '-i', str(identity), 'NewUser@100.69.80.89', 'echo CONNECTED && hostname']

def test_gateway_preserves_permission_denied_text():
    runner = FakeRunner(subprocess.CompletedProcess(['ssh'], 255, '', 'NewUser@100.69.80.89: Permission denied (publickey).\n'))
    result = OpenSshGateway(runner=runner).test_connection(SshTarget('NewUser', '100.69.80.89'), timeout=8)
    assert result == {'ok': False, 'text': 'NewUser@100.69.80.89: Permission denied (publickey).'}
