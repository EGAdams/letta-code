"""The bridge to Toyota's receptionist_team sidecar.

Everything here is offline: `stream_toyota_turn` takes its opener as a keyword
and `preferred_backend` takes its probe, so no test touches loopback. What is
worth asserting is the translation (the browser must see exactly the envelope
`/api/letta-code-stream` emits), the fail-closed behaviour on every unhappy
path, and the backend choice — because a wrong choice there is how Toyota's box
goes mute.
"""
import io
import json

import pytest
import urllib.error
from pydantic import ValidationError

import toyota_service


def _ndjson(*records):
    """A urlopen stand-in that replays sidecar records as an NDJSON body."""
    payload = ''.join(json.dumps(r) + '\n' for r in records).encode()

    class _Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(request, timeout=None):
        return _Response(payload)

    return opener


def _drain(records, **kw):
    request = toyota_service.ToyotaTurnRequest(text='how much did we spend?')
    return list(toyota_service.stream_toyota_turn(
        request, opener=_ndjson(*records), **kw))


class TestTranslationMatchesTheBrowsersEnvelope:
    """The browser parses one wire format; these records must look like Letta's."""

    def test_a_reply_becomes_an_assistant_message_event(self):
        out = _drain([
            {'kind': 'reply', 'text': 'About $4,200.'},
            {'kind': 'result', 'session': 'toyota'},
        ])
        assert out[0].type == 'event'
        assert out[0].event == {
            'message_type': 'assistant_message', 'content': 'About $4,200.'}

    def test_the_acknowledgment_is_an_assistant_message_too(self):
        """It is spoken, so it must ride the same channel as the reply."""
        out = _drain([
            {'kind': 'acknowledgment', 'text': 'Let me check with accounting.'},
            {'kind': 'reply', 'text': 'About $4,200.'},
            {'kind': 'result', 'session': 'toyota'},
        ])
        assert [r.event['content'] for r in out[:2]] == [
            'Let me check with accounting.', 'About $4,200.']

    def test_the_result_carries_the_session_as_the_conversation_id(self):
        out = _drain([{'kind': 'result', 'session': 'toyota'}])
        assert out[-1].event == {'type': 'result', 'conversation_id': 'toyota'}

    def test_an_error_record_becomes_a_failure_record(self):
        out = _drain([{'kind': 'error', 'text': 'RuntimeError: boom'}])
        assert out[0].type == 'error'
        assert 'boom' in out[0].error

    def test_an_unknown_kind_is_dropped_rather_than_guessed_at(self):
        out = _drain([
            {'kind': 'telemetry', 'text': 'ignore me'},
            {'kind': 'result', 'session': 'toyota'},
        ])
        assert [r.event.get('type') for r in out] == ['result']

    def test_an_empty_reply_produces_no_speech(self):
        out = _drain([
            {'kind': 'reply', 'text': '   '},
            {'kind': 'result', 'session': 'toyota'},
        ])
        assert len(out) == 1


class TestTheStreamAlwaysTerminates:
    """The browser's adapter waits for a terminal record; it must always get one."""

    def test_nothing_is_yielded_after_the_result(self):
        out = _drain([
            {'kind': 'result', 'session': 'toyota'},
            {'kind': 'reply', 'text': 'too late'},
        ])
        assert len(out) == 1

    def test_a_stream_that_ends_without_a_result_reports_a_failure(self):
        out = _drain([{'kind': 'reply', 'text': 'half an answer'}])
        assert out[-1].type == 'error'
        assert 'without a result' in out[-1].error

    def test_unparseable_lines_are_skipped_not_fatal(self):
        request = toyota_service.ToyotaTurnRequest(text='hi')

        class _Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        body = (b'not json\n\n'
                + json.dumps({'kind': 'result', 'session': 'toyota'}).encode()
                + b'\n')
        out = list(toyota_service.stream_toyota_turn(
            request, opener=lambda *a, **k: _Response(body)))
        assert out[-1].event == {'type': 'result', 'conversation_id': 'toyota'}


class TestFailClosedOnEveryUnhappyPath:
    def test_a_refused_connection_names_the_unit_to_start(self):
        def opener(*a, **k):
            raise urllib.error.URLError('Connection refused')

        request = toyota_service.ToyotaTurnRequest(text='hi')
        out = list(toyota_service.stream_toyota_turn(request, opener=opener))
        assert out[0].type == 'error'
        assert 'toyota-receptionist' in out[0].error

    def test_an_http_error_surfaces_the_sidecars_own_detail(self):
        def opener(*a, **k):
            raise urllib.error.HTTPError(
                'http://127.0.0.1:8767/turn', 400, 'Bad Request', {},
                io.BytesIO(b'message is empty'))

        request = toyota_service.ToyotaTurnRequest(text='hi')
        out = list(toyota_service.stream_toyota_turn(request, opener=opener))
        assert out[0].type == 'error'
        assert 'message is empty' in out[0].error

    def test_a_broken_stream_is_reported_not_raised(self):
        class _Exploding(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def __next__(self):
                raise OSError('socket closed')

        request = toyota_service.ToyotaTurnRequest(text='hi')
        out = list(toyota_service.stream_toyota_turn(
            request, opener=lambda *a, **k: _Exploding(b'')))
        assert out[0].type == 'error'
        assert 'broke' in out[0].error


class TestRequestValidation:
    def test_a_blank_message_is_rejected(self):
        with pytest.raises(ValidationError):
            toyota_service.ToyotaTurnRequest(text='   \n ')

    def test_control_characters_are_rejected(self):
        with pytest.raises(ValidationError):
            toyota_service.ToyotaTurnRequest(text='hello\x07world')

    def test_carriage_returns_are_normalised_rather_than_rejected(self):
        request = toyota_service.ToyotaTurnRequest(text='one\r\ntwo')
        assert request.text == 'one\ntwo'

    def test_an_oversized_message_is_rejected(self):
        with pytest.raises(ValidationError):
            toyota_service.ToyotaTurnRequest(text='x' * 9000)

    def test_unknown_fields_are_rejected(self):
        with pytest.raises(ValidationError):
            toyota_service.ToyotaTurnRequest(text='hi', brain='letta')

    def test_the_browsers_letta_body_shape_is_accepted_unchanged(self):
        """One adapter posts to both routes, so both bodies must validate."""
        request = toyota_service.ToyotaTurnRequest(
            text='hi', agent='Toyota', conversation_id='abc')
        assert request.text == 'hi'

    def test_only_the_text_is_forwarded_to_the_sidecar(self):
        sent = {}

        class _Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(http_request, timeout=None):
            sent['data'] = json.loads(http_request.data)
            return _Response(
                json.dumps({'kind': 'result', 'session': 'toyota'}).encode() + b'\n')

        request = toyota_service.ToyotaTurnRequest(
            text='hi', agent='Toyota', conversation_id='abc')
        list(toyota_service.stream_toyota_turn(request, opener=opener))
        assert sent['data'] == {'text': 'hi'}


class TestBackendSelection:
    def test_a_healthy_sidecar_wins_by_default(self):
        choice = toyota_service.preferred_backend(
            probe=lambda timeout=None: {'ok': True, 'session': 'toyota'})
        assert choice['backend'] == 'receptionist-team'
        assert choice['forced'] is False
        assert choice['service']['session'] == 'toyota'

    def test_a_dead_sidecar_falls_back_instead_of_leaving_toyota_mute(self):
        choice = toyota_service.preferred_backend(
            probe=lambda timeout=None: {'ok': False, 'error': 'Connection refused'})
        assert choice['backend'] == 'letta'
        assert choice['forced'] is False
        assert choice['service']['error'] == 'Connection refused'

    def test_the_env_override_pins_letta_without_probing(self, monkeypatch):
        monkeypatch.setenv('TOYOTA_CONVERSATION_BACKEND', 'Letta')

        def probe(timeout=None):
            raise AssertionError('a forced backend must not probe')

        choice = toyota_service.preferred_backend(probe=probe)
        assert choice == {'backend': 'letta', 'forced': True, 'service': None}

    def test_an_unrecognised_override_does_not_disable_the_sidecar(self):
        """Only the literal "letta" pins; a typo must not silently downgrade."""
        import os
        os.environ['TOYOTA_CONVERSATION_BACKEND'] = 'reception'
        try:
            choice = toyota_service.preferred_backend(
                probe=lambda timeout=None: {'ok': True})
            assert choice['backend'] == 'receptionist-team'
        finally:
            del os.environ['TOYOTA_CONVERSATION_BACKEND']


class TestHealthNeverRaises:
    def test_a_refused_probe_returns_a_reason(self, monkeypatch):
        def urlopen(*a, **k):
            raise urllib.error.URLError('Connection refused')

        monkeypatch.setattr(toyota_service.urllib.request, 'urlopen', urlopen)
        assert toyota_service.health(timeout=0.1)['ok'] is False

    def test_a_malformed_payload_is_not_treated_as_healthy(self, monkeypatch):
        class _Response(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(
            toyota_service.urllib.request, 'urlopen',
            lambda *a, **k: _Response(b'"a string"'))
        assert toyota_service.health()['ok'] is False
