"""Mazda's two brains, and the choice between them.

Offline: `stream_turn` takes its chooser and both streams as keywords, so no
test touches loopback. What matters here is the choice — a wrong one is how
Mazda's page goes mute or silently keeps talking to the old brain — and the
fact that Letta's ids never cross to the sidecar, which serves one session of
its own.

The record translation itself is shared with Toyota and pinned in
`test_toyota_service.py`; it is not re-asserted here.
"""
import io
import json

import pytest

import mazda_receptionist_service as mrs
import mazda_service


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


def _request(**kw):
    return mazda_service.MazdaTurnRequest(text='verify the January statement', **kw)


class TestWhichBrainAnswers:
    def test_a_healthy_sidecar_wins(self):
        used = []
        records = list(mrs.stream_turn(
            _request(),
            choose=lambda: {'backend': 'receptionist-team'},
            sidecar=lambda r: iter([used.append(('sidecar', r.text)) or 'rec']),
            letta=lambda r: iter([used.append(('letta', r.text)) or 'rec']),
        ))

        assert records == ['rec']
        assert used == [('sidecar', 'verify the January statement')]

    def test_a_dead_sidecar_falls_back_to_letta_instead_of_going_mute(self):
        used = []
        list(mrs.stream_turn(
            _request(),
            choose=lambda: {'backend': 'letta'},
            sidecar=lambda r: iter([used.append('sidecar')]),
            letta=lambda r: iter([used.append('letta')]),
        ))

        assert used == ['letta']

    def test_the_env_override_pins_letta_without_probing(self, monkeypatch):
        monkeypatch.setenv('MAZDA_CONVERSATION_BACKEND', 'letta')
        probed = []

        choice = mrs.preferred_backend(probe=lambda timeout=None: probed.append(1) or {'ok': True})

        assert choice == {'backend': 'letta', 'forced': True, 'service': None}
        assert not probed, 'the override must not even probe the sidecar'

    def test_a_healthy_probe_selects_the_sidecar(self):
        choice = mrs.preferred_backend(probe=lambda timeout=None: {'ok': True, 'agent': 'mazda'})

        assert choice['backend'] == 'receptionist-team'
        assert choice['service']['agent'] == 'mazda'

    def test_a_refused_probe_reports_the_reason_and_falls_back(self):
        choice = mrs.preferred_backend(
            probe=lambda timeout=None: {'ok': False, 'error': 'Connection refused'})

        assert choice['backend'] == 'letta'
        assert choice['forced'] is False
        assert 'refused' in choice['service']['error']


class TestOnlyTheTextCrossesToTheSidecar:
    def test_lettas_ids_are_not_forwarded(self):
        """The sidecar serves one session and reports which one answered, so a
        Letta agent id or conversation id would be meaningless there."""
        sent = []

        def sidecar(request):
            sent.append(request)
            return iter([])

        list(mrs.stream_turn(
            _request(agent=mazda_service.MAZDA_AGENT_ID, request_id='abcdefgh12'),
            choose=lambda: {'backend': 'receptionist-team'},
            sidecar=sidecar,
        ))

        assert sent[0].text == 'verify the January statement'
        assert sent[0].request_id == 'abcdefgh12'
        assert sent[0].agent is None
        assert sent[0].conversation_id is None


class TestTheSidecarStream:
    def test_a_turn_translates_into_the_browsers_envelope(self):
        out = list(mrs.stream_mazda_receptionist_turn(
            mrs.MazdaReceptionistTurnRequest(text='hi'),
            opener=_ndjson(
                {'kind': 'acknowledgment', 'text': 'Let me check with our progress tracker.'},
                {'kind': 'reply', 'text': 'Two reports are missing.'},
                {'kind': 'result', 'session': 'mazda'},
            )))

        assert [r.type for r in out] == ['event', 'event', 'event']
        assert out[0].event['content'] == 'Let me check with our progress tracker.'
        assert out[1].event['content'] == 'Two reports are missing.'
        assert out[2].event['conversation_id'] == 'mazda'

    def test_a_refused_connection_names_her_own_unit_not_toyotas(self):
        import urllib.error

        def opener(request, timeout=None):
            raise urllib.error.URLError('Connection refused')

        out = list(mrs.stream_mazda_receptionist_turn(
            mrs.MazdaReceptionistTurnRequest(text='hi'), opener=opener))

        assert len(out) == 1 and out[0].type == 'error'
        assert 'mazda-receptionist' in out[0].error
        assert 'toyota' not in out[0].error.lower()

    def test_her_port_is_her_own(self):
        assert mrs.MAZDA_SERVICE_URL.endswith(':8768')
        assert mrs.BRIDGE.name == 'Mazda'


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
