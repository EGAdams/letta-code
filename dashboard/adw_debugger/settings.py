"""Where the debugger's settings come from: defaults, then a JSON file, then env.

Read on every request, so the stall timeout changes without a restart or a
source edit:

    dashboard/config/adw_debugger.json   {"stall_timeout_seconds": 45}
    ADW_DEBUGGER_STALL_SECONDS=45        (wins over the file)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .models import DebuggerSettings

DEFAULT_DB = '~/agent_blocks/adws/adw_data/sssf.db'
CONFIG_FILE = Path(__file__).resolve().parent.parent / 'config' / 'adw_debugger.json'


class FileAndEnvSettings:
    """Implements ISettingsSource."""

    def __init__(self, config_file: Path = CONFIG_FILE, environ=None):
        self._config_file = config_file
        self._environ = os.environ if environ is None else environ

    def load(self) -> DebuggerSettings:
        values: dict = {'db_path': DEFAULT_DB}
        try:
            stored = json.loads(self._config_file.read_text(encoding='utf-8'))
            if isinstance(stored, dict):
                values.update(stored)
        except (OSError, ValueError):
            pass
        env = self._environ
        if env.get('ADW_DEBUGGER_DB'):
            values['db_path'] = env['ADW_DEBUGGER_DB']
        if env.get('ADW_DEBUGGER_ADWS'):
            values['adw_names'] = [n.strip() for n in env['ADW_DEBUGGER_ADWS'].split(',') if n.strip()]
        if env.get('ADW_DEBUGGER_STALL_SECONDS'):
            values['stall_timeout_seconds'] = float(env['ADW_DEBUGGER_STALL_SECONDS'])
        values['db_path'] = os.path.expanduser(str(values['db_path']))
        return DebuggerSettings(**values)
