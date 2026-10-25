"""Yes/No questions an agent_blocks ADW puts to whoever is at the dashboard.

An ADW that reaches a step it must not take on its own -- pc_doctor offering
to shut WSL down and compact its disk is the first -- POSTs a question here
and polls for the answer. AdwPromptDialog (js/implementation/
adw-prompt-dialog.js) polls GET /api/adw-prompt and raises a Yes/No modal for
the oldest open question; the click comes back as POST /api/adw-prompt-answer.

The dashboard never acts on an answer. It only records it: the ADW that asked
is the one that reads it back (GET /api/adw-prompt?id=...) and decides what
to do. So a question nobody answers just expires, and a dashboard restart
loses nothing, because the state lives in a JSON file beside this module.

Statuses: pending -> yes | no (answered), withdrawn (the ADW gave up and
said so), expired (nobody answered in time).
"""
import json
import os
import threading
import time
import uuid

from paths import HERE

PROMPTS_FILE = os.path.join(HERE, 'adw_prompts.json')

#: How long a question waits when the ADW does not say.
DEFAULT_EXPIRES_SECONDS = 15 * 60
#: Ceiling on what an ADW may ask for, so a typo can't pin a modal for days.
MAX_EXPIRES_SECONDS = 24 * 60 * 60
#: Answered and expired prompts kept for reading back; older ones are dropped.
KEEP = 50

ANSWERS = ('yes', 'no')

_lock = threading.Lock()


def _now():
    return time.time()


def _load():
    try:
        with open(PROMPTS_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _save(prompts):
    tmp = PROMPTS_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(prompts[-KEEP:], f, indent=2)
    os.replace(tmp, PROMPTS_FILE)


def _expire(prompts, now):
    changed = False
    for p in prompts:
        if p.get('status') == 'pending' and p.get('expires_at', 0) <= now:
            p['status'] = 'expired'
            p['closed_at'] = now
            changed = True
    return changed


def _public(p):
    return {k: p.get(k) for k in (
        'id', 'question', 'detail', 'source', 'status',
        'created_at', 'expires_at', 'closed_at')}


def create_prompt(data):
    """POST /api/adw-prompt: open a question. Needs `question` and `source`."""
    data = data if isinstance(data, dict) else {}
    question = str(data.get('question') or '').strip()
    source = str(data.get('source') or '').strip()
    if not question or not source:
        return {'ok': False, 'error': 'question and source are required'}
    try:
        expires_in = float(data.get('expires_in_seconds') or DEFAULT_EXPIRES_SECONDS)
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'expires_in_seconds must be a number'}
    expires_in = max(10.0, min(expires_in, MAX_EXPIRES_SECONDS))
    now = _now()
    prompt = {
        'id': uuid.uuid4().hex[:12],
        'question': question[:200],
        'detail': str(data.get('detail') or '').strip()[:2000],
        'source': source[:80],
        'status': 'pending',
        'created_at': now,
        'expires_at': now + expires_in,
        'closed_at': None,
    }
    with _lock:
        prompts = _load()
        _expire(prompts, now)
        prompts.append(prompt)
        _save(prompts)
    return {'ok': True, 'prompt': _public(prompt)}


def read_prompt(prompt_id=''):
    """GET /api/adw-prompt[?id=]: one prompt by id, or the oldest open one.

    Without an id this is what the dashboard polls: `active` says whether a
    modal should be up, and `prompt` is the question to show.
    """
    now = _now()
    with _lock:
        prompts = _load()
        if _expire(prompts, now):
            _save(prompts)
    if prompt_id:
        for p in prompts:
            if p.get('id') == prompt_id:
                return {'ok': True, 'prompt': _public(p)}
        return {'ok': False, 'error': f'no prompt {prompt_id}'}
    for p in prompts:
        if p.get('status') == 'pending':
            return {'ok': True, 'active': True, 'prompt': _public(p)}
    return {'ok': True, 'active': False, 'prompt': None}


def _close(prompt_id, status):
    now = _now()
    with _lock:
        prompts = _load()
        _expire(prompts, now)
        for p in prompts:
            if p.get('id') != prompt_id:
                continue
            if p.get('status') != 'pending':
                _save(prompts)
                return {'ok': False, 'error': f'prompt is already {p.get("status")}',
                        'prompt': _public(p)}
            p['status'] = status
            p['closed_at'] = now
            _save(prompts)
            return {'ok': True, 'prompt': _public(p)}
    return {'ok': False, 'error': f'no prompt {prompt_id}'}


def answer_prompt(data):
    """POST /api/adw-prompt-answer: {id, answer: "yes"|"no"} from the modal."""
    data = data if isinstance(data, dict) else {}
    answer = str(data.get('answer') or '').strip().lower()
    if answer not in ANSWERS:
        return {'ok': False, 'error': 'answer must be "yes" or "no"'}
    return _close(str(data.get('id') or ''), answer)


def withdraw_prompt(data):
    """POST /api/adw-prompt-withdraw: {id} -- the asking ADW stopped waiting."""
    data = data if isinstance(data, dict) else {}
    return _close(str(data.get('id') or ''), 'withdrawn')
