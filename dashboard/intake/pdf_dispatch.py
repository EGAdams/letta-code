"""Notifying Mazda that a PDF document is ready for intake processing."""

from __future__ import annotations

import json
import urllib.request
from urllib.parse import quote


def notify_mazda_of_pdf(letta_base_url, file_path, label=None, conversation_id=None,
                        dispatched_at=None, facade_result=None):
    """Background: send a PDF document to Mazda for intake processing."""
    if not conversation_id:
        print('[pdf→mazda] Refusing shared/default conversation dispatch')
        return False
    try:
        label_str = f' "{label}"' if label else ''
        msg = (
            f'A PDF document{label_str} is ready for processing.\n'
            f'The file is at: {file_path}\n\n'
            f'Please process this document through your intake pipeline:\n'
            f'1. Call load_wrapper_revision to load your active wrapper.\n'
            f'2. Classify and parse the document (cheapest reliable tool first).\n'
            f'3. Call record_trace when done to log this run.\n'
            f'4. If anything fails, call propose_improvement with the failure details.'
            f' Every /api/expense-stored callback must include '
            f'"conversation_id":"{conversation_id}" and '
            f'"dispatched_at":{float(dispatched_at or 0)}.'
        )
        payload = json.dumps({
            'messages': [{'role': 'user', 'content': msg}],
            'streaming': False,
        }).encode()
        req = urllib.request.Request(
            f'{letta_base_url}/v1/conversations/{quote(conversation_id, safe="")}/messages',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            print(f'[pdf→mazda] Mazda notified of PDF{label_str}: HTTP {resp.status}; '
                  f'conversation={conversation_id}')
        return True
    except Exception as exc:
        print(f'[pdf→mazda] Failed to notify Mazda: {exc}')
        return False
