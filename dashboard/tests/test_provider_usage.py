"""Tests for monitoring/provider_usage.py, pointed at the owning module.

The interesting half is what the two classifiers now *refuse*. Before this
round both read an unrecognised usage body as a confident all-clear, and that
verdict is what decides whether the ChatGPT failover swap fires -- so the old
behaviour is asserted here as the thing that must never come back.
"""
from __future__ import annotations

import json
import urllib.error

import pytest
from pydantic import ValidationError

import server
from health.failures import classify_failure
from monitoring import provider_usage as pu


# ── Golden payloads: the real shapes, byte-identical verdicts ────────────────

def test_classify_codex_usage_ok_under_limit():
    usage = {'rate_limit': {'allowed': True, 'limit_reached': False,
                            'primary_window': {'used_percent': 37, 'reset_at': 4102444800},
                            'secondary_window': {'used_percent': 44, 'reset_at': 4102444800}}}
    r = pu.classify_codex_usage(usage)
    assert r['ok'] is True
    assert '5h 37%' in r['text'] and 'weekly 44%' in r['text']


def test_classify_codex_usage_flags_maxed_window_as_rate_limit():
    usage = {'rate_limit': {'allowed': True, 'limit_reached': False,
                            'primary_window': {'used_percent': 100, 'reset_at': 4102444800}}}
    r = pu.classify_codex_usage(usage)
    assert r['ok'] is False
    assert r['text'].startswith('llm_rate_limit:')
    assert classify_failure(r['text'])[1] == 'rate-limited'


def test_classify_codex_usage_labels_a_weekly_primary_window_weekly():
    # The 2026-08-19 shape: one primary window that is actually 7 days long.
    usage = {'rate_limit': {'allowed': False, 'limit_reached': True,
                            'primary_window': {'used_percent': 100, 'reset_at': 4102444800,
                                               'limit_window_seconds': 604800},
                            'secondary_window': None}}
    r = pu.classify_codex_usage(usage)
    assert r['ok'] is False
    assert 'weekly window 100% used' in r['text']
    assert '5h window' not in r['text']


def test_classify_codex_usage_respects_limit_reached_flag():
    usage = {'rate_limit': {'allowed': False, 'limit_reached': True,
                            'primary_window': {'used_percent': 63, 'reset_at': 4102444800}}}
    r = pu.classify_codex_usage(usage)
    assert r['ok'] is False and 'llm_rate_limit' in r['text']


def test_classify_codex_usage_respects_allowed_false_with_no_maxed_window():
    usage = {'rate_limit': {'allowed': False, 'limit_reached': False,
                            'primary_window': {'used_percent': 12, 'reset_at': 4102444800}}}
    r = pu.classify_codex_usage(usage)
    assert r == {'ok': False, 'text': 'llm_rate_limit: limit reached'}


def test_classify_claude_usage_contract():
    ok = pu.classify_claude_usage({'five_hour': {'utilization': 12, 'resets_at': None},
                                   'seven_day': {'utilization': 80, 'resets_at': None}})
    assert ok['ok'] is True
    assert ok['text'] == '5h 12% / weekly 80%'
    maxed = pu.classify_claude_usage({'five_hour': {'utilization': 100, 'resets_at': None},
                                      'seven_day': {'utilization': 55, 'resets_at': None}})
    assert maxed['ok'] is False and maxed['text'].startswith('llm_rate_limit:')


def test_codex_window_label_uses_the_declared_duration():
    assert pu.codex_window_label({'limit_window_seconds': 18000}, '?') == '5h'
    assert pu.codex_window_label({'limit_window_seconds': 604800}, '?') == 'weekly'
    assert pu.codex_window_label({'limit_window_seconds': 86400}, '?') == '1d'
    # No duration in the payload — keep the positional name rather than guess.
    assert pu.codex_window_label({}, '5h') == '5h'


def test_codex_window_label_reads_a_model_as_well_as_a_dict():
    """It is called with a CodexWindow internally and with a dict by callers
    that only have raw JSON. Both must keep working."""
    window = pu.CodexWindow(used_percent=1, limit_window_seconds=604800)
    assert pu.codex_window_label(window, '?') == 'weekly'


# ── What the models refuse: the round's headline ─────────────────────────────

@pytest.mark.parametrize('payload,why', [
    ({}, 'no rate_limit key at all'),
    ({'rate_limit': {}}, 'a rate_limit that says nothing'),
    ({'rate_limit': {'allowed': True, 'limit_reached': False}}, 'flags but no window'),
    ({'detail': 'Unauthorized'}, 'an error envelope'),
    ({'rate_limit': None}, 'an explicit null'),
])
def test_codex_payloads_with_no_verdict_are_refused(payload, why):
    """Every one of these used to return {'ok': True, 'text': ''} -- a green
    tile with nothing written on it, meaning "this account has headroom" to
    chatgpt_failover.maybe_failover. A body we no longer understand is not headroom."""
    with pytest.raises(pu.UsagePayloadError):
        pu.classify_codex_usage(payload)


def test_the_old_code_really_did_say_ok_to_a_shapeless_body():
    """The pin for the bug, written as the code that used to run. If this ever
    stops being the old behaviour, the model above stopped earning its keep."""
    def old_classify(usage):
        rl = usage.get('rate_limit') or {}
        windows = []
        for wkey, wfallback in (('primary_window', '5h'), ('secondary_window', 'weekly')):
            w = rl.get(wkey)
            if isinstance(w, dict):
                windows.append((wfallback, float(w.get('used_percent') or 0)))
        maxed = [lbl for lbl, pct in windows if pct >= 100]
        if rl.get('limit_reached') or maxed or not rl.get('allowed', True):
            return {'ok': False, 'text': 'llm_rate_limit:'}
        return {'ok': True, 'text': ' / '.join(lbl for lbl, _ in windows)}

    assert old_classify({'detail': 'Unauthorized'}) == {'ok': True, 'text': ''}
    with pytest.raises(pu.UsagePayloadError):
        pu.classify_codex_usage({'detail': 'Unauthorized'})


def test_a_window_that_will_not_say_how_full_it_is_is_refused():
    """float(w.get('used_percent') or 0) turned both a missing field and a null
    into 0% -- the most reassuring number available."""
    for window in ({'reset_at': 4102444800}, {'used_percent': None, 'reset_at': 1}):
        with pytest.raises(pu.UsagePayloadError):
            pu.classify_codex_usage({'rate_limit': {'primary_window': window}})


def test_an_explicit_cap_is_accepted_with_no_window_at_all():
    """The validator must never turn a real 'you are capped' into an error --
    that would replace a failover trigger with a shrug."""
    r = pu.classify_codex_usage({'rate_limit': {'limit_reached': True}})
    assert r['ok'] is False and r['text'].startswith('llm_rate_limit:')


@pytest.mark.parametrize('payload', [
    {},
    {'error': 'unauthorized'},
    {'five_hour': None, 'seven_day': None},
])
def test_claude_payloads_with_no_window_are_refused(payload):
    """Worse than the codex case: these used to render as '5h 0% / weekly 0%'
    -- a specific, plausible, wrong number rather than merely a blank."""
    with pytest.raises(pu.UsagePayloadError):
        pu.classify_claude_usage(payload)


def test_claude_renders_only_the_windows_that_are_actually_present():
    r = pu.classify_claude_usage({'five_hour': {'utilization': 12}})
    assert r == {'ok': True, 'text': '5h 12%'}
    assert '0%' not in r['text']


def test_extra_unknown_fields_are_tolerated():
    """The vendors add keys. Refusing those would turn every payload change
    into an outage, which is the opposite of what the models are for."""
    r = pu.classify_codex_usage({'rate_limit': {'primary_window': {'used_percent': 5},
                                                'brand_new_key': 1}, 'other': 'x'})
    assert r['ok'] is True


def test_models_dump_to_plain_json_serialisable_dicts():
    """Nothing browser-facing may start carrying a model instance."""
    usage = pu.CodexUsage.model_validate(
        {'rate_limit': {'primary_window': {'used_percent': 5, 'reset_at': 1}}})
    json.dumps(usage.model_dump())


# ── probe_usage_endpoint: how a refusal reaches the caller ───────────────────

class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_a_refused_payload_becomes_a_failure_not_an_exception(monkeypatch):
    monkeypatch.setattr(pu.urllib.request, 'urlopen', lambda *a, **k: _FakeResponse({'nope': 1}))
    r = pu.probe_usage_endpoint('http://x', {}, pu.classify_codex_usage)
    assert r['ok'] is False
    assert r['text'].startswith('usage payload not understood')


def test_a_refused_payload_is_not_labelled_a_rate_limit(monkeypatch):
    """classify_failure() keys off the 'llm_rate_limit:' prefix, and that
    prefix is what makes the failover swap plausible. A renamed JSON key must
    not be able to swap the fleet's account."""
    monkeypatch.setattr(pu.urllib.request, 'urlopen', lambda *a, **k: _FakeResponse({'nope': 1}))
    r = pu.probe_usage_endpoint('http://x', {}, pu.classify_codex_usage)
    assert not r['text'].startswith('llm_rate_limit')
    assert classify_failure(r['text'])[1] != 'rate-limited'


def test_a_shape_error_still_names_the_field_that_broke(monkeypatch):
    """Scrubbing the classifier's trigger words out of the path must not scrub
    the path away -- the operator still needs to know which field moved."""
    monkeypatch.setattr(pu.urllib.request, 'urlopen', lambda *a, **k: _FakeResponse(
        {'rate_limit': {'primary_window': {'reset_at': 1}}}))
    r = pu.probe_usage_endpoint('http://x', {}, pu.classify_codex_usage)
    assert 'primary_window.used_percent' in r['text']
    assert classify_failure(r['text'])[1] != 'rate-limited'


def test_shape_detail_drops_only_the_elements_that_would_mislabel_it():
    err = None
    try:
        pu.CodexUsage.model_validate({'rate_limit': {'primary_window': {'reset_at': 1}}})
    except ValidationError as e:
        err = e
    detail = pu._shape_detail(err)
    assert detail.startswith('primary_window.used_percent:')
    assert 'rate_limit' not in detail


def test_a_scrubbed_away_path_still_leaves_a_noun_in_the_message(monkeypatch):
    """The top-level field IS 'rate_limit', so scrubbing removes the whole
    path. Without a fallback noun the operator's log reads 'Field required'."""
    monkeypatch.setattr(pu.urllib.request, 'urlopen', lambda *a, **k: _FakeResponse({}))
    r = pu.probe_usage_endpoint('http://x', {}, pu.classify_codex_usage)
    assert r['text'] == 'usage payload not understood: the usage block: Field required'
    assert classify_failure(r['text'])[1] != 'rate-limited'


def test_a_401_is_an_auth_failure_not_a_rate_limit(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.HTTPError('http://x', 401, 'Unauthorized', {}, None)
    monkeypatch.setattr(pu.urllib.request, 'urlopen', boom)
    r = pu.probe_usage_endpoint('http://x', {}, pu.classify_codex_usage)
    assert r == {'ok': False, 'text': 'provider OAuth token rejected (HTTP 401)'}


def test_a_429_is_a_rate_limit(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.HTTPError('http://x', 429, 'Too Many', {}, None)
    monkeypatch.setattr(pu.urllib.request, 'urlopen', boom)
    r = pu.probe_usage_endpoint('http://x', {}, pu.classify_codex_usage)
    assert r['ok'] is False and r['text'].startswith('llm_rate_limit:')


def test_a_dead_network_is_a_failure_with_the_reason_in_the_text(monkeypatch):
    def boom(*a, **k):
        raise OSError('connection refused')
    monkeypatch.setattr(pu.urllib.request, 'urlopen', boom)
    r = pu.probe_usage_endpoint('http://x', {}, pu.classify_codex_usage)
    assert r == {'ok': False, 'text': 'connection refused'}


def test_a_good_payload_still_round_trips_through_the_real_fetch(monkeypatch):
    monkeypatch.setattr(pu.urllib.request, 'urlopen', lambda *a, **k: _FakeResponse(
        {'rate_limit': {'primary_window': {'used_percent': 37, 'reset_at': 4102444800},
                        'secondary_window': {'used_percent': 44, 'reset_at': 4102444800}}}))
    r = pu.probe_usage_endpoint('http://x', {}, pu.classify_codex_usage)
    assert r['ok'] is True and '5h 37%' in r['text']


# ── The two vendor probes: headers are the contract ──────────────────────────

def test_probe_codex_usage_sends_the_account_scoped_codex_headers(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen['url'] = req.full_url
        seen['headers'] = {k.lower(): v for k, v in req.headers.items()}
        return _FakeResponse({'rate_limit': {'primary_window': {'used_percent': 1}}})
    monkeypatch.setattr(pu.urllib.request, 'urlopen', fake_urlopen)

    pu.probe_codex_usage({'access_token': 'tok', 'account_id': 'acct'})
    assert seen['url'] == 'https://chatgpt.com/backend-api/wham/usage'
    assert seen['headers']['authorization'] == 'Bearer tok'
    assert seen['headers']['chatgpt-account-id'] == 'acct'


def test_probe_claude_usage_accepts_either_credential_shape(monkeypatch):
    seen = []

    def fake_urlopen(req, timeout=None):
        seen.append({k.lower(): v for k, v in req.headers.items()}['authorization'])
        return _FakeResponse({'five_hour': {'utilization': 1}})
    monkeypatch.setattr(pu.urllib.request, 'urlopen', fake_urlopen)

    pu.probe_claude_usage({'access_token': 'flat'})
    pu.probe_claude_usage({'claudeAiOauth': {'accessToken': 'nested'}})
    assert seen == ['Bearer flat', 'Bearer nested']


def test_probe_registry_covers_every_provider_type_the_fleet_uses():
    """The Mazda fleet is on an anthropic-typed row and Suzuki's on a
    chatgpt_oauth one. A type missing here is silently unprobed -- no error,
    just a fleet nobody is watching."""
    assert set(pu.PROVIDER_USAGE_PROBES) >= {'chatgpt_oauth', 'anthropic', 'anthropic_oauth'}
    assert pu.PROVIDER_USAGE_PROBES['chatgpt_oauth'] is pu.probe_codex_usage
    assert pu.PROVIDER_USAGE_PROBES['anthropic'] is pu.probe_claude_usage


# ── The injected roster ──────────────────────────────────────────────────────

def test_provider_agent_ids_reads_the_injected_roster():
    deps = pu.Collaborators(
        agents=[{'name': 'A', 'llm_provider': 'p', 'id': 'agent-a'},
                {'name': 'B', 'llm_provider': 'other', 'id': 'agent-b'},
                {'name': 'C', 'llm_provider': 'p', 'id': None}],
        get_letta_id=lambda cfg: cfg['id'])
    assert pu.provider_agent_ids('p', deps=deps) == ['agent-a']


def test_provider_agent_ids_skips_agents_with_no_real_id():
    """An agent whose Letta ID cannot be resolved is not "an agent with no
    quota problem" -- it is an agent we cannot flag, and including it would put
    a rate-limit error on a dashboard row for an agent that does not exist."""
    deps = pu.Collaborators(agents=[{'llm_provider': 'p', 'id': 'x'}],
                            get_letta_id=lambda cfg: None)
    assert pu.provider_agent_ids('p', deps=deps) == []


def test_server_builds_the_bundle_fresh_from_its_own_globals(monkeypatch):
    """Rule 4: build it at import and monkeypatching server.LETTA_AGENTS lands
    on a name nothing reads any more."""
    monkeypatch.setattr(server, 'LETTA_AGENTS',
                        [{'name': 'Fake', 'llm_provider': 'zzz', 'id': 'agent-fake'}])
    monkeypatch.setattr(server, 'get_letta_id', lambda cfg: cfg['id'])
    assert server._provider_agent_ids('zzz') == ['agent-fake']


def test_production_wires_the_real_collaborators():
    deps = server._provider_usage_deps()
    assert deps.agents is server.LETTA_AGENTS
    assert deps.get_letta_id is server.get_letta_id


def test_the_real_fleet_is_still_reachable_through_the_wrapper():
    """Unpatched, against the real roster: the Suzuki fleet and the Mazda fleet
    are each tagged with a provider that has a probe registered."""
    for provider in (server.CHATGPT_PLUS_PRO, server.CLAUDE_PRO_MAX):
        assert server._provider_agent_ids(provider), provider


# ── What server.py re-exports, and what it must not ──────────────────────────

@pytest.mark.parametrize('server_name,module_name', [
    ('PROVIDER_USAGE_PROBES', 'PROVIDER_USAGE_PROBES'),
    ('_fetch_provider_oauth_creds', 'fetch_provider_oauth_creds'),
])
def test_server_re_exports_the_owning_modules_object(server_name, module_name):
    assert getattr(server, server_name) is getattr(pu, module_name)


def test_the_probe_registry_is_the_same_dict_the_failover_poll_reads():
    """tests/test_chatgpt_failover.py patches it with monkeypatch.setitem.
    That only works because both bindings are the module's own dict, not a
    copy -- the sweep reads it through monitoring.chatgpt_failover, and
    chatgpt_provider_health reads it through server."""
    assert server.PROVIDER_USAGE_PROBES is pu.PROVIDER_USAGE_PROBES


@pytest.mark.parametrize('name', [
    '_classify_codex_usage', '_classify_claude_usage', '_probe_usage_endpoint',
    '_probe_claude_usage', 'codex_window_label', 'CodexUsage', 'ClaudeUsage',
])
def test_dead_re_exports_are_gone_from_server(name):
    assert not hasattr(server, name), f'server.{name} is a dead re-export'
