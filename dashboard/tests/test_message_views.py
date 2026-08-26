"""Tests for agents/message_views.py -- the Thoughts, Messages and Tool Calls tabs.

Pointed at the owning module, never at `server`. The code under test closes
over its own module globals, so `monkeypatch.setattr(server, 'X', ...)` would
isolate nothing here while looking exactly like it did.

`letta_messages`, `letta_get` and `_msg_age_seconds` stay in server.py and
arrive through `Collaborators`, so nothing here needs a Letta server.
"""
import time
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

import server
from agents import message_views
from agents.message_views import (
    Collaborators,
    ConversationMessages,
    cached_thoughts,
    letta_convo,
    letta_thoughts,
    letta_toolcalls,
    within_max_age,
)

NOW = 1_800_000_000.0


def _boom(name):
    def fail(*a, **k):
        raise AssertionError(f'{name} must not be called here')
    return fail


def _deps(messages=None, get=None, age=None):
    """A bundle whose unused halves fail loudly rather than returning None."""
    return Collaborators(
        letta_messages=messages if messages is not None else _boom('letta_messages'),
        letta_get=get if get is not None else _boom('letta_get'),
        msg_age_seconds=age if age is not None else (lambda m, now: 0.0),
    )


def _msg(message_type, text, created_at='2026-08-12T19:07:44Z', **extra):
    payload = {'message_type': message_type, 'created_at': created_at}
    key = {'reasoning_message': 'reasoning'}.get(message_type, 'content')
    payload[key] = text
    payload.update(extra)
    return payload


# ==========================================================================
# ConversationMessages -- the one untyped fetch path
# ==========================================================================
class TestConversationMessages:
    def test_a_bare_list_is_accepted(self):
        assert ConversationMessages(messages=[{'a': 1}]).messages == [{'a': 1}]

    @pytest.mark.parametrize('key', ['messages', 'results'])
    def test_both_envelopes_are_accepted(self, key):
        assert ConversationMessages(messages={key: [{'a': 1}]}).messages == [{'a': 1}]

    def test_the_messages_envelope_wins_over_results(self):
        payload = {'messages': [{'from': 'messages'}], 'results': [{'from': 'results'}]}

        assert ConversationMessages(messages=payload).messages == [{'from': 'messages'}]

    def test_a_null_messages_key_is_refused(self):
        """`.get('messages', fallback)` returns the stored None rather than the
        fallback, because the key is present -- so None, not a list, used to
        reach select_thoughts, and the failure landed several frames from its
        cause."""
        with pytest.raises(ValidationError):
            ConversationMessages(messages={'messages': None})

    def test_an_unrecognised_envelope_is_refused_rather_than_emptied(self):
        """The old code turned this into [], which renders identically to an
        agent that has genuinely said nothing. Only one of those is a bug."""
        with pytest.raises(ValidationError) as exc:
            ConversationMessages(messages={'data': [{'a': 1}], 'total': 1})

        assert 'messages' in str(exc.value) and 'results' in str(exc.value)

    @pytest.mark.parametrize('payload', ['a string', 42, True])
    def test_a_scalar_payload_is_refused(self, payload):
        with pytest.raises(ValidationError):
            ConversationMessages(messages=payload)

    def test_non_object_entries_are_refused(self):
        """Every reader downstream calls .get() on each entry."""
        with pytest.raises(ValidationError):
            ConversationMessages(messages=['just a string'])

    def test_an_empty_conversation_is_fine(self):
        assert ConversationMessages(messages=[]).messages == []


class TestConversationFetch:
    def test_a_failed_fetch_is_still_an_empty_tab(self):
        """letta_get returns None on any network error. That is a network fact,
        not a shape change, and the tab has always shown it as empty."""
        rows = letta_thoughts('agent-mazda', 'conv-window',
                              deps=_deps(get=lambda path, timeout=0: None))

        assert rows == []

    def test_the_conversation_endpoint_is_called_with_the_slow_relay_timeout(self):
        seen = {}

        def fake_get(path, timeout=0):
            seen.update(path=path, timeout=timeout)
            return []

        letta_thoughts('agent-mazda', 'conv-window', deps=_deps(get=fake_get))

        assert seen == {
            'path': '/v1/conversations/conv-window/messages?limit=80',
            'timeout': 25,
        }

    def test_the_conversation_id_is_url_quoted(self):
        seen = {}

        def fake_get(path, timeout=0):
            seen['path'] = path
            return []

        letta_thoughts('agent-mazda', 'conv/with slash', deps=_deps(get=fake_get))

        assert 'conv%2Fwith%20slash' in seen['path']

    def test_a_shape_change_raises_rather_than_emptying_the_tab(self):
        with pytest.raises(ValidationError):
            letta_thoughts('agent-mazda', 'conv-window',
                           deps=_deps(get=lambda path, timeout=0: {'data': []}))

    def test_the_proxy_turns_that_raise_into_a_kept_last_value(self, capsys):
        """cached_thoughts is what the route actually calls, and the proxy
        catches loader exceptions -- so a shape change costs a log line and the
        previous answer, not a 500 and not a blank tab."""
        deps = _deps(get=lambda path, timeout=0: {'data': []})

        assert cached_thoughts('agent-shapechange', 'conv-x', deps=deps) == []
        _drain_proxy()

        assert 'refresh failed' in capsys.readouterr().out


def _drain_proxy(timeout=2.0):
    """Wait for the background refresh the last cached_thoughts call submitted."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        futures = [e['future'] for e in message_views._thoughts_proxy._entries.values()]
        if all(f is None or f.done() for f in futures):
            return
        time.sleep(0.01)


# ==========================================================================
# The Thoughts tab
# ==========================================================================
class TestLettaThoughts:
    @pytest.mark.parametrize(('message', 'expected_type'), [
        ({'message_type': 'reasoning_message', 'reasoning': 'x' * 700}, 'thought'),
        ({'message_type': 'assistant_message', 'content': 'x' * 700}, None),
        ({'message_type': 'user_message', 'content': 'x' * 700}, 'user'),
    ])
    def test_entries_are_not_truncated(self, message, expected_type):
        """A thought is the thing you read when something went wrong; a preview
        of it is worth very little."""
        rows = letta_thoughts(
            'agent-test', deps=_deps(messages=lambda agent_id, limit: [message]))

        assert rows[0]['text'] == 'x' * 700
        if expected_type is None:
            assert 'type' not in rows[0]
        else:
            assert rows[0]['type'] == expected_type

    def test_an_isolated_conversation_replaces_agent_history(self):
        """A scanner run has its own conversation; mixing in agent-wide history
        would show thoughts from an unrelated task alongside it."""
        rows = letta_thoughts(
            'agent-mazda', 'conv-window',
            deps=_deps(get=lambda path, timeout=0: [{
                'message_type': 'reasoning_message',
                'created_at': '2026-08-12T19:07:44Z',
                'reasoning': 'I am processing this Window scan.',
            }]))

        assert rows == [{
            'date': '2026-08-12T19:07:44',
            'type': 'thought',
            'text': 'I am processing this Window scan.',
        }]

    def test_no_conversation_id_reads_agent_history(self):
        rows = letta_thoughts('agent-mazda', '', deps=_deps(
            messages=lambda agent_id, limit: [_msg('reasoning_message', 'from history')]))

        assert rows[0]['text'] == 'from history'


class TestCachedThoughts:
    def test_it_serves_the_cache_while_a_refresh_runs(self, monkeypatch):
        class FakeProxy:
            def get(self, key, *args, default=None):
                assert key == ('agent-mazda', 'conv-freezer')
                assert args[1:] == ('agent-mazda', 'conv-freezer')
                return [{'text': 'cached'}]

        monkeypatch.setattr(message_views, '_thoughts_proxy', FakeProxy())

        started = time.monotonic()
        rows = cached_thoughts('agent-mazda', 'conv-freezer', deps=_deps())

        assert time.monotonic() - started < 0.1
        assert rows == [{'text': 'cached'}]

    def test_full_history_is_keyed_by_agent(self, monkeypatch):
        """Two agents with no active scan conversation must not share one entry
        -- the old scanner-only key was just the conversation_id, so both fell
        into the same '' bucket."""
        class FakeProxy:
            def get(self, key, *args, default=None):
                return key

        monkeypatch.setattr(message_views, '_thoughts_proxy', FakeProxy())

        assert (cached_thoughts('agent-mazda', '', deps=_deps())
                != cached_thoughts('agent-suzuki', '', deps=_deps()))

    def test_the_deps_bundle_is_not_part_of_the_cache_key(self, monkeypatch):
        """The bundle is rebuilt per call, so keying on it would make every
        call a miss and defeat the proxy entirely."""
        keys = []

        class FakeProxy:
            def get(self, key, *args, default=None):
                keys.append(key)
                return []

        monkeypatch.setattr(message_views, '_thoughts_proxy', FakeProxy())

        cached_thoughts('agent-mazda', '', deps=_deps())
        cached_thoughts('agent-mazda', '', deps=_deps())

        assert keys[0] == keys[1]


# ==========================================================================
# The Messages tab
# ==========================================================================
class TestLettaConvo:
    def test_it_keeps_only_the_user_assistant_exchange(self):
        msgs = [_msg('user_message', 'hi'), _msg('assistant_message', 'hello'),
                _msg('reasoning_message', 'hmm'), _msg('tool_call_message', 'run')]

        rows = letta_convo('a', deps=_deps(messages=lambda agent_id, limit: msgs))

        assert [r['type'] for r in rows] == ['user_message', 'assistant_message']

    def test_rows_carry_date_type_and_text(self):
        rows = letta_convo('a', deps=_deps(
            messages=lambda agent_id, limit: [_msg('user_message', 'hi')]))

        assert rows == [{'date': '2026-08-12T19:07:44', 'type': 'user_message',
                         'text': 'hi'}]

    def test_old_messages_are_dropped(self):
        ages = {'old': message_views.MESSAGES_MAX_AGE_SECONDS + 1, 'new': 5}
        msgs = [_msg('user_message', 'old'), _msg('user_message', 'new')]

        rows = letta_convo('a', deps=_deps(
            messages=lambda agent_id, limit: msgs,
            age=lambda m, now: ages[m['content']]))

        assert [r['text'] for r in rows] == ['new']

    def test_blank_messages_are_dropped(self):
        msgs = [_msg('user_message', '   '), _msg('user_message', 'real')]

        rows = letta_convo('a', deps=_deps(messages=lambda agent_id, limit: msgs))

        assert [r['text'] for r in rows] == ['real']

    def test_it_asks_for_the_agent_history_limit(self):
        seen = {}

        def fake_messages(agent_id, limit):
            seen.update(agent_id=agent_id, limit=limit)
            return []

        letta_convo('agent-42', deps=_deps(messages=fake_messages))

        assert seen == {'agent_id': 'agent-42', 'limit': 200}


class TestWithinMaxAge:
    def test_an_unparseable_timestamp_is_shown(self):
        """Fail-open on purpose: dropping a message is the less recoverable
        mistake of the two."""
        assert within_max_age({}, NOW, deps=_deps(age=lambda m, now: None)) is True

    def test_the_boundary_is_inclusive(self):
        limit = message_views.MESSAGES_MAX_AGE_SECONDS

        assert within_max_age({}, NOW, deps=_deps(age=lambda m, now: limit)) is True
        assert within_max_age({}, NOW, deps=_deps(age=lambda m, now: limit + 1)) is False


# ==========================================================================
# The Tool Calls tab
# ==========================================================================
class TestLettaToolcalls:
    def test_it_keeps_only_calls_and_returns(self):
        msgs = [_msg('tool_call_message', 'run', tool_call={'name': 'grep'}),
                _msg('tool_return_message', 'done'),
                _msg('user_message', 'hi')]

        rows = letta_toolcalls('a', deps=_deps(messages=lambda agent_id, limit: msgs))

        assert [r['type'] for r in rows] == ['grep', 'tool_return']

    def test_an_unnamed_call_falls_back_to_a_label(self):
        msgs = [_msg('tool_call_message', 'run')]

        rows = letta_toolcalls('a', deps=_deps(messages=lambda agent_id, limit: msgs))

        assert rows[0]['type'] == 'tool_call'

    def test_long_output_is_truncated(self):
        """Unlike a thought, a tool return is often a whole file; the tab is a
        list, not a reader."""
        msgs = [_msg('tool_return_message', 'x' * 900)]

        rows = letta_toolcalls('a', deps=_deps(messages=lambda agent_id, limit: msgs))

        assert rows[0]['text'] == 'x' * 300

    def test_there_is_no_age_filter(self):
        """A tool call is evidence of what the agent did, and this tab is read
        after the fact -- the Messages tab's 5-hour window would hide it."""
        msgs = [_msg('tool_return_message', 'ancient')]

        rows = letta_toolcalls('a', deps=_deps(
            messages=lambda agent_id, limit: msgs,
            age=_boom('msg_age_seconds')))

        assert [r['text'] for r in rows] == ['ancient']

    def test_blank_entries_are_dropped(self):
        msgs = [_msg('tool_return_message', ''), _msg('tool_return_message', 'real')]

        rows = letta_toolcalls('a', deps=_deps(messages=lambda agent_id, limit: msgs))

        assert [r['text'] for r in rows] == ['real']


# ==========================================================================
# How server.py wires it
# ==========================================================================
class TestServerWiring:
    def test_the_wrapper_passes_the_real_collaborators(self):
        deps = server._message_view_deps()

        assert deps.letta_messages is server.letta_messages
        assert deps.letta_get is server.letta_get
        assert deps.msg_age_seconds is server._msg_age_seconds

    @pytest.mark.parametrize('name', ['letta_messages', 'letta_get', '_msg_age_seconds'])
    def test_the_wrapper_resolves_each_name_at_call_time(self, monkeypatch, name):
        """The bundle is built per call, so replacing any of these on `server`
        is honoured. Built at import instead, the patch would land on a name
        nothing calls any more."""
        sentinel = object()
        monkeypatch.setattr(server, name, sentinel)

        deps = server._message_view_deps()

        field = {'letta_messages': 'letta_messages', 'letta_get': 'letta_get',
                 '_msg_age_seconds': 'msg_age_seconds'}[name]
        assert getattr(deps, field) is sentinel

    def test_the_tab_wrappers_reach_the_moved_code(self, monkeypatch):
        """End to end through the real server.py wrapper, real age filter and
        real timestamp parsing -- only the Letta fetch is replaced."""
        fresh = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        monkeypatch.setattr(
            server, 'letta_messages',
            lambda agent_id, limit: [_msg('user_message', 'wired', created_at=fresh)])

        assert [r['text'] for r in server.letta_convo('a')] == ['wired']

    def test_the_real_age_filter_drops_a_stale_message(self, monkeypatch):
        """The same path, with a timestamp outside the 5-hour window. Proves
        the wrapper is wiring the real _msg_age_seconds, not a permissive stub."""
        stale = (datetime.now(timezone.utc)
                 - timedelta(seconds=message_views.MESSAGES_MAX_AGE_SECONDS + 60))
        monkeypatch.setattr(
            server, 'letta_messages',
            lambda agent_id, limit: [_msg('user_message', 'ancient',
                                          created_at=stale.strftime('%Y-%m-%dT%H:%M:%SZ'))])

        assert server.letta_convo('a') == []

    def test_the_claude_log_age_filter_still_works_through_server(self, monkeypatch):
        """http_app calls srv._within_max_age for the local Claude Code log,
        which has no Letta agent behind it at all."""
        monkeypatch.setattr(server, '_msg_age_seconds', lambda m, now: 10)

        assert server._within_max_age({'date': 'now'}, NOW) is True

    @pytest.mark.parametrize('name', [
        'letta_thoughts', '_msg_date', '_letta_conversation_messages',
        '_thoughts_proxy', 'MESSAGES_MAX_AGE_SECONDS',
    ])
    def test_server_does_not_re_export_the_moved_names(self, name):
        assert not hasattr(server, name), (
            f'server.{name} is a dead re-export -- a second binding a test can '
            f'patch while the real one keeps running')

    @pytest.mark.parametrize('name', ['cached_thoughts', 'letta_convo',
                                      'letta_toolcalls', '_within_max_age'])
    def test_the_names_http_app_uses_are_still_reachable(self, name):
        """http_app/get_routes.py reaches these through `srv`, so dropping one
        would break a route with the suite still green."""
        assert callable(getattr(server, name))
