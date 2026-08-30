"""Validity-based status for the two EG ChatGPT OAuth credential copies."""

import base64
import json

from chatgpt_provider_status import chatgpt_provider_account_status


def _token(email: str, exp: int) -> str:
    payload = {
        'exp': exp,
        'https://api.openai.com/profile': {'email': email},
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    return f'header.{encoded}.signature'


def test_expired_provider_with_valid_same_account_recommends_sync():
    status = chatgpt_provider_account_status(
        {'access_token': _token('eg1972@gmail.com', 100)},
        local_auth={'tokens': {'access_token': _token('eg1972@gmail.com', 300)}},
        probe={'ok': False, 'text': 'HTTP 401'}, now=200)

    assert status.provider_token_state == 'expired'
    assert status.local_token_state == 'valid'
    assert status.sync_recommended is True
    assert status.incident_id


def test_different_but_valid_tokens_are_considered_in_sync():
    status = chatgpt_provider_account_status(
        {'access_token': _token('eg1972@gmail.com', 250)},
        local_auth={'tokens': {'access_token': _token('eg1972@gmail.com', 300)}},
        probe={'ok': True, 'text': 'weekly 10% used'}, now=200)

    assert status.provider_token_state == 'valid'
    assert status.local_token_state == 'valid'
    assert status.sync_recommended is False


def test_rejected_unexpired_provider_is_stale_and_recommends_sync():
    status = chatgpt_provider_account_status(
        {'access_token': _token('eg1972@gmail.com', 250)},
        local_auth={'tokens': {'access_token': _token('eg1972@gmail.com', 300)}},
        probe={'ok': False, 'text': 'HTTP 401'}, now=200)

    assert status.provider_token_state == 'stale'
    assert status.sync_recommended is True
