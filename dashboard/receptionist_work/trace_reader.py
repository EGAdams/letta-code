"""Read only this assignment's ADW events, keeping links usable on a phone."""
import json
import re

from .contracts import FINANCE_ROOT


def trace(run_id: str, state) -> dict:
    if not re.fullmatch(r'[a-f0-9]{8}', run_id) or run_id not in state.run_ids:
        raise ValueError('That run is not part of this receptionist assignment.')
    path = FINANCE_ROOT / 'adws/adw_data/sessions' / run_id / 'events.jsonl'
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {'ok': True, 'run_id': run_id, 'events': events[-500:]}
