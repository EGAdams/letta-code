"""Tests for monitoring/chatgpt_failover.py, pointed at the owning module.

The expensive half of this module is what it does to the *standby* file: a
heal overwrites the only parked copy of the second account's refresh token,
and a rotating token means the overwritten one is gone for good. So the tests
that matter most are the ones about what it refuses to write.

`StandbyCredentials` is asserted here both ways -- what it now rejects, and
what the shipped code used to do with exactly those bundles, written out as
the old code inline so the day the model stops earning its keep is visible.
"""
from __future__ import annotations

import json
import subprocess

import pytest
from pydantic import ValidationError

import chatgpt_provider_accounts
import server
from health.failures import classify_failure
from hosts import LETTA_DOCKER_HOST
from monitoring import chatgpt_failover as cf


#: The real bundle's shape, read off the live standby file on 2026-08-26.
LIVE_SHAPE = {
    'access_token': 'eyJhbGciOiJSUzI1NiJ9.body.sig',
    'refresh_token': 'rt.1.AAAcnrFPIgknj',
    'account_id': 'df86beca-c3c8-4640-0000-000000000000',
    'expires_at': 1788013060,
}


def _creds(**over):
    return cf.StandbyCredentials.model_validate({**LIVE_SHAPE, **over})


@pytest.fixture(autouse=True)
def _clean_state():
    """Module state is process-wide; no test may inherit another's cooldown."""
    before = dict(cf._state)
    cf._state.update({'last_swap_ts': 0.0, 'last_note': ''})
    yield
    cf._state.update(before)


# ── The typed boundary: what a standby bundle must say ───────────────────────

def test_the_live_standby_shape_validates_and_round_trips_unchanged():
    assert _creds().as_creds() == LIVE_SHAPE


def test_unknown_vendor_keys_survive_the_round_trip():
    # extra='allow' on purpose: the swap script copies the provider row
    # verbatim, so a key OpenAI adds must not turn a working standby into an
    # error the next time anything reads it.
    raw = {**LIVE_SHAPE, 'id_token': 'eyJ.x', 'auth_mode': 'chatgpt'}
    assert cf.StandbyCredentials.model_validate(raw).as_creds() == raw


@pytest.mark.parametrize('raw', [
    {},
    {'access_token': 'live-token'},
    {'account_id': None, 'refresh_token': None},
    {**LIVE_SHAPE, 'account_id': ''},
])
def test_a_bundle_with_no_account_is_refused(raw):
    with pytest.raises(ValidationError):
        cf.StandbyCredentials.model_validate(raw)


@pytest.mark.parametrize('raw', ['a string', [], 3])
def test_a_standby_file_that_is_not_an_object_is_refused(raw):
    with pytest.raises(ValidationError):
        cf.StandbyCredentials.model_validate(raw)


def test_a_refresh_only_bundle_is_accepted_because_it_is_healable():
    # access_token is NOT required: a parked bundle whose access token has
    # expired (or was never written) is exactly what heal_standby_token
    # exists for. Refusing it would delete a working recovery path.
    creds = cf.StandbyCredentials.model_validate(
        {'account_id': 'acct-a', 'refresh_token': 'rt-standby'})
    assert creds.access_token == ''
    assert cf.codex_refresh_candidates(creds, []) == ['rt-standby']


def test_the_old_code_parked_another_accounts_token_from_these_bundles():
    """What the shipped code did with the bundles the model now refuses.

    This is `codex_refresh_candidates` as it stood before round 10 -- the
    guard is `if account and ...`, so an absent `account_id` did not fail, it
    switched the guard OFF. Every bundle in the parametrize above then yielded
    a refresh token belonging to a DIFFERENT ChatGPT account, which
    heal_standby_token would write back over the real standby.
    """
    def old_codex_refresh_candidates(standby_creds, auth_bundles):
        account = standby_creds.get('account_id')
        ordered = [standby_creds.get('refresh_token')]
        for data in auth_bundles:
            tokens = (data or {}).get('tokens') or {}
            if account and tokens.get('account_id') != account:
                continue
            ordered.append(tokens.get('refresh_token'))
        seen, out = set(), []
        for rt in ordered:
            if rt and rt not in seen:
                seen.add(rt)
                out.append(rt)
        return out

    someone_else = [{'tokens': {'account_id': 'SOMEONE-ELSE',
                                'refresh_token': 'rt-not-ours'}}]
    for bundle in ({}, {'access_token': 'live-token'},
                   {'account_id': None, 'refresh_token': None}):
        assert old_codex_refresh_candidates(bundle, someone_else) == ['rt-not-ours']
    # and with the account present, old and new agree exactly
    good = {'account_id': 'acct-a', 'refresh_token': 'rt-standby'}
    assert old_codex_refresh_candidates(good, someone_else) == ['rt-standby']
    assert cf.codex_refresh_candidates(
        cf.StandbyCredentials.model_validate(good), someone_else) == ['rt-standby']


# ── An error message is an input to something (rule 10) ──────────────────────

def test_a_refused_bundle_is_not_reported_as_a_rate_limit(monkeypatch):
    # These notes reach chatgpt_provider_health's tile text, and
    # http_app/get_routes.py hands tile text straight to classify_failure.
    monkeypatch.setattr(cf.subprocess, 'run',
                        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, '{}', ''))
    creds, err = cf.read_standby_creds()
    assert creds is None
    assert 'account_id' in err
    assert classify_failure(err) == ('error', 'error')


def test_a_shape_error_naming_a_ratelimit_field_still_classifies_as_error(monkeypatch):
    # shape_detail drops path elements that would mislabel the message. A
    # vendor key called `rate_limit` in the bundle must not make "I cannot read
    # this file" read as "the account is capped".
    class Nested(cf.StandbyCredentials):
        rate_limit: int
    try:
        Nested.model_validate(LIVE_SHAPE)
    except ValidationError as e:
        detail = cf.shape_detail(e)
    assert classify_failure(detail) == ('error', 'error')
    assert detail.strip() != ''  # a scrubbed path still leaves a noun


def test_a_genuinely_capped_standby_is_still_labelled_rate_limited():
    # The scrubbing must not go the other way: a real cap keeps its label.
    note = 'standby also limited (llm_rate_limit: 5h window 100% used)'
    assert classify_failure(note)[1] == 'rate-limited'


# ── Pure decisions ───────────────────────────────────────────────────────────

def test_failover_triggers_on_rate_limit_after_cooldown():
    assert cf.failover_should_trigger(
        'llm_rate_limit: 5h window 100% used, resets in 1h',
        now_ts=10_000, last_swap_ts=0, min_interval=1800)


def test_failover_respects_cooldown():
    assert not cf.failover_should_trigger(
        'llm_rate_limit: 5h window 100% used, resets in 1h',
        now_ts=1000, last_swap_ts=0, min_interval=1800)


def test_failover_ignores_non_rate_limit_errors():
    # Auth/network failures must NOT trigger a swap — the standby token would
    # inherit the same problem and the swap burns the cooldown window.
    for text in ('HTTP 401: unauthorized', 'probe timed out', ''):
        assert not cf.failover_should_trigger(
            text, now_ts=10_000, last_swap_ts=0, min_interval=1800)


def test_failover_min_interval_defaults_to_the_module_constant(monkeypatch):
    monkeypatch.setattr(cf, 'CHATGPT_FAILOVER_MIN_INTERVAL', 1800)
    assert not cf.failover_should_trigger('llm_rate_limit: x', now_ts=100, last_swap_ts=0)
    assert cf.failover_should_trigger('llm_rate_limit: x', now_ts=1801, last_swap_ts=0)


def test_standby_verdict_separates_a_capped_account_from_a_stale_token():
    assert cf.standby_probe_verdict({'ok': True, 'text': '5h 12%'}) == 'headroom'
    assert cf.standby_probe_verdict(
        {'ok': False, 'text': 'llm_rate_limit: 5h window 100% used'}) == 'limited'
    # The bug this fixes: an expired parked token used to read as "also limited",
    # so a healable standby looked like a genuinely exhausted second account.
    assert cf.standby_probe_verdict(
        {'ok': False, 'text': 'provider OAuth token rejected (HTTP 401)'}) == 'stale'


def test_codex_refresh_candidates_prefers_standby_then_matching_local_logins():
    standby = cf.StandbyCredentials.model_validate(
        {'account_id': 'acct-a', 'refresh_token': 'rt-standby'})
    bundles = [
        {'tokens': {'account_id': 'acct-a', 'refresh_token': 'rt-live'}},
        {'tokens': {'account_id': 'acct-b', 'refresh_token': 'rt-other-account'}},
        {'tokens': {'account_id': 'acct-a', 'refresh_token': 'rt-standby'}},  # dup
        {'tokens': {'account_id': 'acct-a'}},                                 # no token
    ]
    assert cf.codex_refresh_candidates(standby, bundles) == ['rt-standby', 'rt-live']


def test_codex_refresh_candidates_never_parks_another_accounts_token():
    standby = cf.StandbyCredentials.model_validate(
        {'account_id': 'acct-a', 'refresh_token': None})
    bundles = [{'tokens': {'account_id': 'acct-b', 'refresh_token': 'rt-other-account'}}]
    assert cf.codex_refresh_candidates(standby, bundles) == []


def test_codex_refresh_candidates_skips_a_local_bundle_with_no_account():
    # An auth.json that never got an account_id is not "matches everything".
    standby = cf.StandbyCredentials.model_validate(
        {'account_id': 'acct-a', 'refresh_token': None})
    assert cf.codex_refresh_candidates(standby, [{'tokens': {'refresh_token': 'rt-?'}}]) == []


# ── Reading and writing the parked file ──────────────────────────────────────

def _ssh_returning(stdout, rc=0, stderr='', sink=None):
    def fake_run(cmd, **kw):
        if sink is not None:
            sink.append((cmd, kw.get('input')))
        return subprocess.CompletedProcess(cmd, rc, stdout, stderr)
    return fake_run


def test_read_standby_creds_returns_the_parsed_bundle(monkeypatch):
    monkeypatch.setattr(cf.subprocess, 'run', _ssh_returning(json.dumps(LIVE_SHAPE)))
    creds, err = cf.read_standby_creds()
    assert err is None and creds.account_id == LIVE_SHAPE['account_id']


@pytest.mark.parametrize('stdout,rc,expect', [
    ('', 0, 'missing/unreadable'),
    ('{...', 0, 'standby read failed'),
    ('{}', 1, 'missing/unreadable'),
    ('[]', 0, 'unreadable'),
])
def test_read_standby_creds_names_what_went_wrong(monkeypatch, stdout, rc, expect):
    monkeypatch.setattr(cf.subprocess, 'run', _ssh_returning(stdout, rc=rc))
    creds, err = cf.read_standby_creds()
    assert creds is None and expect in err


def test_write_standby_creds_writes_temp_then_renames(monkeypatch):
    sink = []
    monkeypatch.setattr(cf.subprocess, 'run', _ssh_returning('', sink=sink))
    ok, note = cf.write_standby_creds(_creds())
    assert (ok, note) == (True, 'ok')
    (cmd, payload), = sink
    remote = cmd[-1]
    # A half-written standby file is a destroyed standby file: the swap script
    # can read it at any moment.
    assert remote.startswith('umask 077 && cat > ') and ' && mv ' in remote
    assert cf.CHATGPT_FAILOVER_STANDBY_FILE + '.new' in remote
    assert json.loads(payload) == LIVE_SHAPE


def test_write_standby_creds_reports_the_remote_stderr(monkeypatch):
    monkeypatch.setattr(cf.subprocess, 'run',
                        _ssh_returning('', rc=255, stderr='Permission denied\n'))
    ok, note = cf.write_standby_creds(_creds())
    assert ok is False and 'Permission denied' in note


# ── Healing ──────────────────────────────────────────────────────────────────

def test_heal_refreshes_and_parks_the_rotated_token(monkeypatch):
    written = []
    monkeypatch.setattr(cf, 'local_codex_bundles', lambda: [])
    monkeypatch.setattr(cf, 'codex_refresh', lambda rt, timeout=25: {
        'access_token': 'fresh-at', 'refresh_token': 'rt-rotated', 'expires_in': 3600})
    monkeypatch.setattr(cf, 'write_standby_creds',
                        lambda c: (written.append(c) or (True, 'ok')))
    healed, note = cf.heal_standby_token(_creds())
    assert note == 'standby token refreshed'
    assert healed.access_token == 'fresh-at'
    # Rotating tokens are single-use: failing to store the new one means the
    # next heal has nothing left to try.
    assert healed.refresh_token == 'rt-rotated'
    assert written == [healed]


def test_heal_keeps_the_old_access_token_when_the_refresh_reply_has_none(monkeypatch):
    monkeypatch.setattr(cf, 'local_codex_bundles', lambda: [])
    monkeypatch.setattr(cf, 'codex_refresh',
                        lambda rt, timeout=25: {'access_token': None, 'expires_in': 3600})
    monkeypatch.setattr(cf, 'write_standby_creds', lambda c: (True, 'ok'))
    healed, _note = cf.heal_standby_token(_creds())
    # Parking a null access token would make the standby unprobeable and the
    # tile would then call it "unusable after refresh" forever.
    assert healed.access_token == LIVE_SHAPE['access_token']


def test_heal_tries_the_next_candidate_when_a_refresh_raises(monkeypatch):
    tried = []

    def flaky(rt, timeout=25):
        tried.append(rt)
        if rt == 'rt-standby':
            raise OSError('refresh token already used')
        return {'access_token': 'fresh-at', 'expires_in': 3600}
    monkeypatch.setattr(cf, 'local_codex_bundles', lambda: [
        {'tokens': {'account_id': 'acct-a', 'refresh_token': 'rt-local'}}])
    monkeypatch.setattr(cf, 'codex_refresh', flaky)
    monkeypatch.setattr(cf, 'write_standby_creds', lambda c: (True, 'ok'))
    creds = cf.StandbyCredentials.model_validate(
        {'account_id': 'acct-a', 'refresh_token': 'rt-standby'})
    healed, _note = cf.heal_standby_token(creds)
    assert tried == ['rt-standby', 'rt-local'] and healed.access_token == 'fresh-at'


def test_heal_reports_a_write_back_failure_rather_than_claiming_success(monkeypatch):
    monkeypatch.setattr(cf, 'local_codex_bundles', lambda: [])
    monkeypatch.setattr(cf, 'codex_refresh',
                        lambda rt, timeout=25: {'access_token': 'fresh-at', 'expires_in': 3600})
    monkeypatch.setattr(cf, 'write_standby_creds', lambda c: (False, 'disk full'))
    healed, note = cf.heal_standby_token(_creds())
    assert healed is None and 'write-back failed' in note


def test_heal_with_no_working_token_asks_for_an_interactive_login(monkeypatch):
    monkeypatch.setattr(cf, 'local_codex_bundles', lambda: [])
    monkeypatch.setattr(cf, 'codex_refresh',
                        lambda rt, timeout=25: (_ for _ in ()).throw(OSError('400')))
    healed, note = cf.heal_standby_token(_creds())
    assert healed is None and 'codex login' in note
    assert classify_failure(note) == ('error', 'error')


def test_a_standby_file_with_no_account_never_reaches_a_write(monkeypatch):
    """End to end: the defect the model was added for cannot happen.

    The parked file has lost its account_id and this box is logged into a
    DIFFERENT ChatGPT account. Before round 10 this sequence rewrote the
    standby file with that other account's refresh token.
    """
    monkeypatch.setattr(cf.subprocess, 'run', _ssh_returning('{"access_token": "x"}'))
    monkeypatch.setattr(cf, 'local_codex_bundles', lambda: [
        {'tokens': {'account_id': 'SOMEONE-ELSE', 'refresh_token': 'rt-not-ours'}}])

    def _never(*a, **k):
        raise AssertionError('a bundle we cannot read must never be written back')
    monkeypatch.setattr(cf, 'write_standby_creds', _never)
    monkeypatch.setattr(cf, 'codex_refresh', _never)
    ok, note = cf.standby_has_headroom()
    assert ok is False and 'unreadable' in note


# ── standby_has_headroom ─────────────────────────────────────────────────────

def _probing(*results):
    seq = list(results)
    return lambda creds, timeout=20: seq.pop(0)


def test_headroom_when_the_standby_probe_is_clean(monkeypatch):
    monkeypatch.setattr(cf, 'read_standby_creds', lambda: (_creds(), None))
    monkeypatch.setattr(cf, 'probe_codex_usage', _probing({'ok': True, 'text': '5h 12%'}))
    assert cf.standby_has_headroom() == (True, 'standby has headroom (5h 12%)')


def test_a_capped_standby_is_never_healed(monkeypatch):
    monkeypatch.setattr(cf, 'read_standby_creds', lambda: (_creds(), None))
    monkeypatch.setattr(cf, 'probe_codex_usage',
                        _probing({'ok': False, 'text': 'llm_rate_limit: 5h window 100% used'}))

    def _never(*a, **k):
        raise AssertionError('a rate limit is not something a refresh can fix')
    monkeypatch.setattr(cf, 'heal_standby_token', _never)
    ok, note = cf.standby_has_headroom()
    assert ok is False and note.startswith('standby also limited')


def test_a_stale_standby_is_healed_and_re_probed(monkeypatch):
    monkeypatch.setattr(cf, 'read_standby_creds', lambda: (_creds(), None))
    monkeypatch.setattr(cf, 'probe_codex_usage', _probing(
        {'ok': False, 'text': 'provider OAuth token rejected (HTTP 401)'},
        {'ok': True, 'text': '5h 3%'}))
    monkeypatch.setattr(cf, 'heal_standby_token',
                        lambda c: (_creds(access_token='fresh'), 'standby token refreshed'))
    assert cf.standby_has_headroom() == (True, 'standby has headroom (5h 3%)')


def test_a_stale_standby_that_stays_stale_says_so(monkeypatch):
    monkeypatch.setattr(cf, 'read_standby_creds', lambda: (_creds(), None))
    monkeypatch.setattr(cf, 'probe_codex_usage', _probing(
        {'ok': False, 'text': 'HTTP 401'}, {'ok': False, 'text': 'HTTP 401'}))
    monkeypatch.setattr(cf, 'heal_standby_token', lambda c: (_creds(), 'refreshed'))
    ok, note = cf.standby_has_headroom()
    assert ok is False and note.startswith('standby token unusable after refresh')


def test_a_read_error_is_passed_through_untouched(monkeypatch):
    monkeypatch.setattr(cf, 'read_standby_creds', lambda: (None, 'standby token file missing/unreadable'))
    assert cf.standby_has_headroom() == (False, 'standby token file missing/unreadable')


# ── maybe_failover: the state machine ────────────────────────────────────────

def test_no_swap_inside_the_cooldown(monkeypatch):
    cf._state['last_swap_ts'] = 1_000_000.0
    monkeypatch.setattr(cf.time, 'time', lambda: 1_000_001.0)

    def _never(*a, **k):
        raise AssertionError('cooldown must be checked before anything is read')
    monkeypatch.setattr(cf, 'standby_has_headroom', _never)
    assert cf.maybe_failover({'text': 'llm_rate_limit: capped'}, 'chatgpt-plus-pro') is None


def test_a_standby_with_no_headroom_records_the_note_and_keeps_the_cooldown(monkeypatch):
    monkeypatch.setattr(cf, 'standby_has_headroom', lambda: (False, 'standby also limited (x)'))
    assert cf.maybe_failover({'text': 'llm_rate_limit: capped'}, 'chatgpt-plus-pro') is None
    assert cf.last_failover_note() == 'standby also limited (x)'
    # No attempt was made, so the next sweep may still try.
    assert cf._state['last_swap_ts'] == 0.0


def test_a_failed_swap_still_starts_the_cooldown(monkeypatch):
    monkeypatch.setattr(cf, 'standby_has_headroom', lambda: (True, 'standby has headroom (5h 2%)'))
    monkeypatch.setattr(cf, 'run_failover_swap', lambda: (False, 'swap exited 1'))
    assert cf.maybe_failover({'text': 'llm_rate_limit: capped'}, 'chatgpt-plus-pro') is None
    # Otherwise a broken swap script is retried every 90 seconds forever.
    assert cf._state['last_swap_ts'] > 0
    assert cf.last_failover_note() == 'swap exited 1'


def test_a_successful_swap_re_probes_the_newly_installed_token(monkeypatch):
    monkeypatch.setattr(cf, 'standby_has_headroom', lambda: (True, 'standby has headroom (5h 2%)'))
    monkeypatch.setattr(cf, 'run_failover_swap', lambda: (True, 'SWAP_OK'))
    monkeypatch.setattr(cf, 'fetch_provider_oauth_creds',
                        lambda name: ({'access_token': 'new'}, 'chatgpt_oauth'))
    monkeypatch.setattr(cf, 'probe_codex_usage', lambda creds, timeout=20: {'ok': True, 'text': '5h 2%'})
    # The point of re-probing: the sweep must report the NEW token's state, not
    # leave the whole fleet flagged with the old account's rate limit.
    assert cf.maybe_failover({'text': 'llm_rate_limit: capped'}, 'chatgpt-plus-pro') == {
        'ok': True, 'text': '5h 2%'}


def test_a_re_probe_that_explodes_does_not_undo_the_swap(monkeypatch):
    monkeypatch.setattr(cf, 'standby_has_headroom', lambda: (True, 'ok'))
    monkeypatch.setattr(cf, 'run_failover_swap', lambda: (True, 'SWAP_OK'))
    monkeypatch.setattr(cf, 'fetch_provider_oauth_creds',
                        lambda name: (_ for _ in ()).throw(OSError('letta down')))
    assert cf.maybe_failover({'text': 'llm_rate_limit: capped'}, 'chatgpt-plus-pro') is None
    assert cf.last_failover_note() == 'SWAP_OK'


def test_run_failover_swap_needs_the_scripts_own_success_marker(monkeypatch):
    monkeypatch.setattr(cf.subprocess, 'run', _ssh_returning('done\nSWAP_OK\n'))
    assert cf.run_failover_swap()[0] is True
    monkeypatch.setattr(cf.subprocess, 'run', _ssh_returning('done\n'))
    # rc 0 is not success here: the script prints SWAP_OK only when the row
    # actually changed.
    assert cf.run_failover_swap()[0] is False


# ── The sweep ────────────────────────────────────────────────────────────────

def _deps(recorded, cleared, ids=('a1', 'a2')):
    return cf.Collaborators(
        provider_agent_ids=lambda name: list(ids),
        record_send_error=lambda aid, text: recorded.append((aid, text)),
        clear_send_error=lambda aid: cleared.append(aid))


def _patch_probe(monkeypatch, result, calls=None):
    monkeypatch.setattr(cf, 'fetch_provider_oauth_creds',
                        lambda name: ({'access_token': 't', 'account_id': 'a'}, 'chatgpt_oauth'))

    def fake_probe(creds, timeout=20):
        if calls is not None:
            calls.append(creds)
        return result
    monkeypatch.setitem(cf.PROVIDER_USAGE_PROBES, 'chatgpt_oauth', fake_probe)


def test_a_429_flags_every_agent_on_that_provider(monkeypatch):
    recorded, cleared = [], []
    _patch_probe(monkeypatch, {'ok': False, 'text': 'llm_rate_limit: too many requests'})
    monkeypatch.setattr(cf, 'maybe_failover', lambda probe, name: None)
    cf.poll_provider_once('chatgpt-plus-pro', deps=_deps(recorded, cleared))
    assert [a for a, _t in recorded] == ['a1', 'a2']
    assert all('rate-limited' in t for _a, t in recorded) and cleared == []


def test_a_clean_probe_clears_every_agent_on_that_provider(monkeypatch):
    recorded, cleared = [], []
    _patch_probe(monkeypatch, {'ok': True, 'text': '5h 37% / weekly 44%'})
    cf.poll_provider_once('chatgpt-plus-pro', deps=_deps(recorded, cleared))
    assert cleared == ['a1', 'a2'] and recorded == []


def test_one_usage_call_covers_the_whole_fleet_and_no_agent_is_messaged(monkeypatch):
    # The old 'ping' canary burned ~40 full-context LLM calls per hour against
    # the very quota it was watching (2026-07-07).
    calls, recorded, cleared = [], [], []
    _patch_probe(monkeypatch, {'ok': True, 'text': ''}, calls=calls)

    def _no_llm(*a, **k):
        raise AssertionError('the sweep must not POST to any agent')
    monkeypatch.setattr(cf.urllib.request, 'urlopen', _no_llm)
    cf.poll_provider_once('chatgpt-plus-pro', deps=_deps(recorded, cleared, ids=('a1',) * 7))
    assert len(calls) == 1


def test_a_letta_api_outage_leaves_agent_state_alone(monkeypatch):
    # Letta down != quota exhausted; Server Management owns that signal.
    recorded, cleared = [], []
    monkeypatch.setattr(cf, 'fetch_provider_oauth_creds',
                        lambda name: (_ for _ in ()).throw(OSError('connection refused')))
    cf.poll_provider_once('chatgpt-plus-pro', deps=_deps(recorded, cleared))
    assert recorded == [] and cleared == []


@pytest.mark.parametrize('creds,ptype', [(None, 'chatgpt_oauth'), ({'access_token': 't'}, 'ollama')])
def test_no_token_or_no_probe_for_the_type_leaves_agent_state_alone(monkeypatch, creds, ptype):
    recorded, cleared = [], []
    monkeypatch.setattr(cf, 'fetch_provider_oauth_creds', lambda name: (creds, ptype))
    cf.poll_provider_once('chatgpt-plus-pro', deps=_deps(recorded, cleared))
    assert recorded == [] and cleared == []


def test_a_provider_with_no_agents_is_not_probed(monkeypatch):
    def _never(*a, **k):
        raise AssertionError('nothing is affected, so nothing needs probing')
    monkeypatch.setattr(cf, 'fetch_provider_oauth_creds', _never)
    cf.poll_provider_once('nobody-uses-this', deps=_deps([], [], ids=()))


def test_only_chatgpt_oauth_failures_reach_the_failover(monkeypatch):
    # The Mazda fleet's anthropic row shares this sweep; a Claude rate limit
    # must never swap the ChatGPT provider's token.
    monkeypatch.setattr(cf, 'fetch_provider_oauth_creds',
                        lambda name: ({'access_token': 't'}, 'anthropic'))
    monkeypatch.setitem(cf.PROVIDER_USAGE_PROBES, 'anthropic',
                        lambda creds, timeout=20: {'ok': False, 'text': 'llm_rate_limit: capped'})

    def _never(*a, **k):
        raise AssertionError('failover is a ChatGPT-account concern only')
    monkeypatch.setattr(cf, 'maybe_failover', _never)
    recorded = []
    cf.poll_provider_once('claude-pro-max', deps=_deps(recorded, []))
    assert len(recorded) == 2


def test_a_successful_failover_reports_the_new_tokens_state(monkeypatch):
    recorded, cleared = [], []
    _patch_probe(monkeypatch, {'ok': False, 'text': 'llm_rate_limit: capped'})
    monkeypatch.setattr(cf, 'maybe_failover', lambda probe, name: {'ok': True, 'text': '5h 2%'})
    cf.poll_provider_once('chatgpt-plus-pro', deps=_deps(recorded, cleared))
    assert cleared == ['a1', 'a2'] and recorded == []


# ── The loop ─────────────────────────────────────────────────────────────────

def test_the_loop_survives_a_sweep_that_raises(monkeypatch):
    sweeps = []

    def boom():
        sweeps.append(1)
        raise RuntimeError('transient')

    def stop(_interval):
        if len(sweeps) >= 3:
            raise KeyboardInterrupt
    monkeypatch.setattr(cf.time, 'sleep', stop)
    with pytest.raises(KeyboardInterrupt):
        cf.poll_loop(boom, interval=0)
    assert len(sweeps) == 3


def test_the_loop_calls_the_sweep_it_was_given_each_time(monkeypatch):
    # It takes a callable, not a provider name, precisely so the caller's
    # Collaborators bundle is rebuilt per iteration rather than frozen when
    # the thread started.
    calls = []
    monkeypatch.setattr(cf.time, 'sleep',
                        lambda i: (_ for _ in ()).throw(KeyboardInterrupt) if len(calls) >= 2 else None)
    with pytest.raises(KeyboardInterrupt):
        cf.poll_loop(lambda: calls.append(1), interval=0)
    assert len(calls) == 2


# ── How server.py wires it ───────────────────────────────────────────────────

def test_production_wires_the_real_collaborators():
    deps = server._chatgpt_failover_deps()
    assert deps.provider_agent_ids is server._provider_agent_ids
    assert deps.record_send_error is server.record_agent_send_error
    assert deps.clear_send_error is server.clear_agent_send_error


def test_the_bundle_is_rebuilt_per_call(monkeypatch):
    """Late binding, not a bundle captured at import."""
    monkeypatch.setattr(server, '_provider_agent_ids', lambda name: ['patched'])
    assert server._chatgpt_failover_deps().provider_agent_ids('anything') == ['patched']


def test_the_server_wrapper_sweeps_the_default_provider(monkeypatch):
    seen = []
    monkeypatch.setattr(server.chatgpt_failover, 'poll_provider_once',
                        lambda name, *, deps: seen.append(name))
    server._poll_chatgpt_provider_once()
    assert seen == [server.CHATGPT_PLUS_PRO]


def test_the_poll_loop_thread_body_goes_through_the_server_wrapper(monkeypatch):
    seen = []
    monkeypatch.setattr(server.chatgpt_failover, 'poll_loop', lambda fn, **kw: seen.append(fn))
    server._chatgpt_provider_poll_loop()
    assert seen == [server._poll_chatgpt_provider_once]


def test_the_provider_tile_reads_the_note_through_the_public_verb(monkeypatch):
    # get_routes hands this tile's text to classify_failure, so the note has
    # to arrive as text, not as a poke into module state.
    monkeypatch.setattr(server, '_fetch_provider_oauth_creds',
                        lambda name: ({'access_token': 't'}, 'chatgpt_oauth'))
    monkeypatch.setitem(server.PROVIDER_USAGE_PROBES, 'chatgpt_oauth',
                        lambda creds, timeout=8: {'ok': False, 'text': 'HTTP 401'})
    cf._state['last_note'] = 'standby also limited (llm_rate_limit: 5h 100%)'
    result = server.chatgpt_provider_health()
    assert result['ok'] is False and result['hard'] is True
    assert 'auto-failover: standby also limited' in result['text']


def test_the_provider_tile_offers_the_restart_when_there_is_no_note(monkeypatch):
    monkeypatch.setattr(server, '_fetch_provider_oauth_creds',
                        lambda name: ({'access_token': 't'}, 'chatgpt_oauth'))
    monkeypatch.setitem(server.PROVIDER_USAGE_PROBES, 'chatgpt_oauth',
                        lambda creds, timeout=8: {'ok': False, 'text': 'HTTP 401'})
    assert 'Restart swaps to the standby account token' in server.chatgpt_provider_health()['text']


def test_restart_chatgpt_provider_runs_the_swap_and_refreshes_the_fleet(monkeypatch):
    monkeypatch.setattr(server, '_log_restart', lambda text: None)
    monkeypatch.setattr(server.chatgpt_failover, 'run_failover_swap', lambda: (True, 'SWAP_OK'))
    swept = []
    monkeypatch.setattr(server, '_poll_chatgpt_provider_once', lambda: swept.append(1))
    result = server.restart_chatgpt_provider()
    # The tabs must go green now, not in 90 seconds.
    assert result['ok'] is True and swept == [1]


def test_the_startup_banner_names_the_modules_interval():
    assert server.CHATGPT_PROVIDER_POLL_INTERVAL is cf.CHATGPT_PROVIDER_POLL_INTERVAL


@pytest.mark.parametrize('name', [
    'CHATGPT_FAILOVER_HOST', 'CHATGPT_FAILOVER_MIN_INTERVAL',
    'CHATGPT_FAILOVER_STANDBY_FILE', 'CHATGPT_FAILOVER_SWAP_CMD',
    'CODEX_LOCAL_AUTH', 'CODEX_OAUTH_CLIENT_ID', '_chatgpt_failover',
    '_codex_refresh', '_heal_standby_token', '_local_codex_bundles',
    '_maybe_chatgpt_failover', '_read_standby_creds', '_run_chatgpt_failover_swap',
    '_standby_has_headroom', '_write_standby_creds', 'codex_refresh_candidates',
    'failover_should_trigger', 'standby_probe_verdict',
    # only the failover cluster still probed Codex through `server`
    '_probe_codex_usage',
])
def test_dead_re_exports_are_gone_from_server(name):
    """Nothing calls these through `server` any more. Asserting their absence is
    what stops a future round quietly re-adding a second binding -- and a
    re-export is not harmless: the moved code closes over its OWN module
    global, so patching the server-side name isolates nothing while looking
    exactly like it does."""
    assert not hasattr(server, name), f'server.{name} is a dead re-export'


# ── One destination, one definition ──────────────────────────────────────────

def test_the_letta_box_is_named_once():
    # Three independent copies of this ssh destination existed before; that is
    # how you end up swapping a token on one box and probing another.
    assert cf.CHATGPT_FAILOVER_HOST is LETTA_DOCKER_HOST
    assert chatgpt_provider_accounts.CHATGPT_FAILOVER_HOST is LETTA_DOCKER_HOST
    assert cf.CHATGPT_FAILOVER_STANDBY_FILE == chatgpt_provider_accounts.CHATGPT_STANDBY_FILE
