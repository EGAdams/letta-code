"""The health-check contract, and the two flags that change what the operator sees.

Ninety-two return statements in server.py build the same small dict by hand.
`ProbeResult` names it once. The tests here are mostly about the two optional
flags, because they are the two that do something:

  `concern` turns a tab yellow — up, but wanting attention.
  `hard` suppresses the Restart button, because the cause is somewhere a click
  cannot reach: an expired OAuth token, a quota that resets on its own schedule,
  a credential that only an interactive login regenerates.

Getting `hard` wrong is the expensive one. Drop it and the dashboard offers a
button that cannot possibly work, in front of an operator who will press it,
twice, before concluding the dashboard is lying. So it is pinned from both
sides: that it reaches the payload, and that `compute_server_status` still
honours it.

`tests/test_server.py` covers what each individual check decides. What is
pinned here is the shape they all share.
"""
import pytest
from pydantic import ValidationError

import server
from health import document_vision as docvision
from health import frita
from health.failures import classify_failure
from health.probe import ProbeResult, probe


class TestTheOrdinaryAnswer:
    def test_it_is_exactly_two_keys(self):
        """The eight sub-check rollups iterate these. Defaulting the optional
        flags in would give every one of them two keys it never had."""
        assert probe(True, 'everything fine') == {'ok': True, 'text': 'everything fine'}

    def test_ok_and_text_come_out_in_that_order(self):
        assert list(probe(False, 'dead')) == ['ok', 'text']

    def test_a_check_must_say_something(self):
        """A dot with no words tells the reader that something is fine or
        broken, but not what — which is the one thing they came for."""
        with pytest.raises(ValidationError):
            probe(True, '')

    def test_ok_must_be_stated(self):
        with pytest.raises(ValidationError):
            ProbeResult(text='no verdict')

    def test_a_misspelled_flag_is_refused_rather_than_carried(self):
        """`extra='forbid'` is the point: `hard_failure=True` would otherwise
        ride along in the payload and be read by nobody."""
        with pytest.raises(ValidationError):
            probe(False, 'x', hard_failure=True)


class TestTheConcernFlag:
    def test_it_appears_only_when_true(self):
        assert probe(True, 'degraded', concern=True)['concern'] is True
        assert 'concern' not in probe(True, 'fine', concern=False)

    def test_a_concerned_check_is_still_ok(self):
        """Yellow is a state of being up. A check that sets concern and ok
        together must not read as down anywhere."""
        out = probe(True, 'ghost on :8797', concern=True)
        assert out['ok'] is True

    def test_the_status_computation_turns_it_yellow(self):
        assert server.compute_server_status(
            {'ok': True, 'text': 'x', 'concern': True}) == 'concern'

    def test_without_it_the_same_reading_is_green(self):
        assert server.compute_server_status({'ok': True, 'text': 'x'}) == 'up'


class TestTheHardFlag:
    def test_it_appears_only_when_true(self):
        assert probe(False, 'token expired', hard=True)['hard'] is True
        assert 'hard' not in probe(False, 'crashed')

    def test_a_restartable_service_that_failed_softly_offers_the_button(self):
        """The control: an ordinary failure on a restartable service is
        yellow, because pressing Restart is a real thing to try."""
        assert server.compute_server_status(
            {'ok': False, 'text': 'crashed'}, restartable=True) == 'concern'

    def test_a_hard_failure_does_not(self):
        """The whole reason the flag exists. Nothing this box can do fixes an
        expired credential on someone else's account."""
        assert server.compute_server_status(
            {'ok': False, 'text': 'token expired', 'hard': True},
            restartable=True) == 'down'

    def test_the_categorizer_uses_it_when_every_tier_is_failing(self, tmp_path,
                                                                monkeypatch):
        """The live case: a quota reset, a new key, an interactive login —
        every remedy is somewhere a Restart click cannot reach."""
        import json
        import time
        path = tmp_path / 'provider_health.json'
        path.write_text(json.dumps({
            'gemini:default': {'last_success': 0, 'last_failure': time.time(),
                               'last_failure_detail': '429 quota exceeded'},
        }))
        monkeypatch.setattr(docvision, 'MAZDA_PROVIDER_HEALTH_PATH', str(path))
        out = docvision.mazda_categorizer_fallback_health()
        assert out['ok'] is False and out['hard'] is True


class TestTheSubCheckShape:
    def test_a_named_sub_check_keeps_its_name(self):
        out = ProbeResult(ok=True, text='reachable', name='ssh').to_payload()
        assert out == {'ok': True, 'text': 'reachable', 'name': 'ssh'}

    def test_the_name_comes_before_the_flags(self):
        out = ProbeResult(ok=False, text='x', name='ssh', hard=True).to_payload()
        assert list(out) == ['ok', 'text', 'name', 'hard']

    def test_an_unnamed_check_carries_no_name_key(self):
        assert 'name' not in probe(True, 'x')


class TestNamingTheFailure:
    """The function that stopped a 404 being reported as a throttle.

    Somebody once waited for a quota window to reset while a route was simply
    missing, because 404 fell through to a generic branch and rate-limiting was
    the guess. The ordering is the fix, so the ordering is what is tested.
    """

    @pytest.mark.parametrize('text, kind', [
        ('HTTP 429 Too Many Requests', 'rate_limit'),
        ('rate limit exceeded', 'rate_limit'),
        ('quota exhausted', 'rate_limit'),
        ('HTTP 401 Unauthorized', 'auth'),
        ('403 Forbidden', 'auth'),
        ('invalid_api_key', 'auth'),
        ('HTTP Error 404: Not Found', 'not_found'),
        ('operation timed out', 'timeout'),
        ('Connection refused', 'refused'),
        ('Name or service not known', 'unreachable'),
        ('no route to host', 'unreachable'),
    ])
    def test_each_condition_is_named(self, text, kind):
        assert classify_failure(text)[0] == kind

    def test_a_404_is_not_reported_as_a_throttle(self):
        """The specific regression. Stated on its own because the parametrised
        case above would still pass if 404 were merely categorised as
        something else wrong."""
        assert classify_failure('HTTP Error 404: Not Found')[1] == 'provider error (404)'

    def test_an_unrecognised_error_is_not_guessed_at(self):
        assert classify_failure('segmentation fault') == ('error', 'error')

    @pytest.mark.parametrize('value', ['', None])
    def test_no_error_text_is_not_a_crash(self, value):
        assert classify_failure(value) == ('error', 'error')

    def test_matching_is_case_insensitive(self):
        assert classify_failure('RATE LIMIT')[0] == 'rate_limit'

    def test_a_message_naming_two_conditions_takes_the_earlier_rule(self):
        """Deliberate: the ladder is ordered, and a throttle that also
        mentions a timeout is still a throttle."""
        assert classify_failure('429 rate limited; request timed out')[0] == 'rate_limit'

    def test_it_has_one_definition(self):
        """Five checks call it, so it lives beside none of them."""
        assert server.classify_failure is classify_failure


class TestThePatchTargetTrap:
    """These probes reach real machines. Aiming a stub at `server` misses.

    This one has bitten three times in this refactor, and its signature is the
    worst kind: the test passes, having quietly talked to the live executor on
    :8799 instead of the stub. Six frita tests were doing exactly that.
    """

    @pytest.mark.parametrize('module, name', [
        (frita, '_probe_sdk_status'),
        (frita, '_resync_frita_creds'),
        (frita, 'FRITA_EXEC_GOOD_URL'),
        (docvision, 'MAZDA_PROVIDER_HEALTH_PATH'),
        (docvision, 'ROL_FINANCES_ENV_PATH'),
    ])
    def test_the_global_lives_on_its_own_module(self, module, name):
        assert name in vars(module)

    def test_stubbing_the_probe_on_server_does_not_stop_the_network_call(
            self, monkeypatch):
        """Demonstrated, not described. The stub on `server` is ignored; the
        one on `frita` is what the check actually calls."""
        calls = []
        monkeypatch.setattr(server, '_probe_sdk_status',
                            lambda *a, **k: calls.append('server-stub'))
        monkeypatch.setattr(frita, '_probe_sdk_status',
                            lambda *a, **k: calls.append('frita-stub'))
        monkeypatch.setattr(frita, '_resync_frita_creds', lambda t: False)
        frita.frita_executor_health(timeout=1)
        assert 'server-stub' not in calls
        assert 'frita-stub' in calls


class TestServerReExports:
    @pytest.mark.parametrize('name, module', [
        ('frita_executor_health', frita),
        ('_probe_sdk_status', frita),
        ('FRITA_EXEC_WORK_URL', frita),
        ('document_vision_health', docvision),
        ('mazda_categorizer_fallback_health', docvision),
        ('DOCUMENT_VISION_HALT_MESSAGE', docvision),
        ('unresolved_fallbacks', docvision),
    ])
    def test_the_historical_name_still_resolves(self, name, module):
        assert getattr(server, name) is getattr(module, name)

    def test_the_registry_still_finds_the_moved_checks(self):
        """SERVERS entries name their check as a string; a moved function that
        was not re-exported would be a KeyError at the first health sweep."""
        assert server.HEALTH_CHECKS['frita_executor_health'] is frita.frita_executor_health
