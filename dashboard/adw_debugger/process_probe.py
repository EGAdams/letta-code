"""IProcessProbe over /proc: is that pid still the ADW it was recorded as?"""
from __future__ import annotations

from pathlib import Path


class ProcProcessProbe:
    def alive(self, pid: int, command: str) -> bool:
        try:
            cmdline = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode('utf-8', 'replace')
        except OSError:
            return False
        script = command.split(' ', 1)[0] if command else ''
        return script in cmdline          # a recycled pid running something else is not this run
