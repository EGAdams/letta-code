"""The Automatic / Semi-Automatic switch.

The expensive failure this file guards is a switch that says "Mazda Automatic"
while the dispatch fork is still blocking, or the reverse: an operator who
believes Mazda is off and scans a stack of documents she then reads at full
price. So the mode the API reports and the mode `_dispatch_mazda_or_block`
branches on are asserted to be the same value, not merely consistent-looking.
"""

import json
import os
import re

import pytest

from intake.mazda_mode import (
    AUTOMATIC,
    MAZDA_MODE_LABELS,
    SEMI_AUTOMATIC,
    ExecutionModeConfig,
    InMemoryMazdaModeStore,
    InvalidExecutionMode,
    JsonFileMazdaModeStore,
    MazdaMode,
    MazdaModeRequest,
    MazdaModeService,
    MazdaModeState,
    resolve_execution_mode,
    state_for,
)

DASHBOARD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODE_INTERFACE_JS = os.path.join(
    DASHBOARD_DIR, 'js', 'abstract', 'mazda-mode.interface.js')


# ── the two positions ──────────────────────────────────────────────────────

def test_automatic_is_the_pipelines_own_word():
    """The wire values stay 'auto'/'human_only'. Every stored intake record,
    status message and test already says them; renaming would rewrite intake
    history to mean the same thing differently."""
    assert AUTOMATIC == 'auto'
    assert SEMI_AUTOMATIC == 'human_only'


def test_state_for_derives_everything_from_the_mode():
    automatic = state_for(AUTOMATIC, source='operator')
    assert automatic.automatic is True
    assert automatic.label == 'Mazda Automatic'
    semi = state_for(SEMI_AUTOMATIC, source='operator')
    assert semi.automatic is False
    assert semi.label == 'Mazda Semi-Automatic'


def test_state_for_refuses_an_unknown_mode():
    with pytest.raises(ValueError):
        state_for('semi', source='operator')


def test_state_refuses_a_label_that_does_not_name_a_real_mode():
    """A label is the only thing the operator reads. One that says something
    the mode does not mean is the whole failure this module exists to avoid."""
    with pytest.raises(Exception):
        MazdaModeState(mode='auto', automatic=True, label='Mazda On',
                       source='operator')


# ── the request ────────────────────────────────────────────────────────────

def test_request_is_a_boolean_not_a_mode_name():
    assert MazdaModeRequest.from_http({'automatic': True}).mode == AUTOMATIC
    assert MazdaModeRequest.from_http({'automatic': False}).mode == SEMI_AUTOMATIC


def test_missing_flag_reads_as_semi_automatic():
    """Fail toward the mode that spends nothing. A body that forgot the flag
    must never be the thing that switches paid reading on."""
    assert MazdaModeRequest.from_http({}).mode == SEMI_AUTOMATIC


def test_request_refuses_a_non_object_body():
    with pytest.raises(ValueError):
        MazdaModeRequest.from_http(['automatic'])


@pytest.mark.parametrize('value', ['maybe', 'false', 'true', 1, 0, None, {}])
def test_truthy_junk_never_switches_mazda_on(value):
    """Caught by a live smoke test: bool("maybe") is True, so a typo'd body
    turned paid reading on and answered ok. Only a real boolean moves this
    switch."""
    with pytest.raises(Exception):
        MazdaModeRequest.from_http({'automatic': value})


def test_a_rejected_body_leaves_the_switch_alone():
    service = MazdaModeService(InMemoryMazdaModeStore(), default_mode=SEMI_AUTOMATIC)
    out = service.set_from_http({'automatic': 'maybe'})
    assert out['ok'] is False
    assert service.mode() == SEMI_AUTOMATIC


# ── the service ────────────────────────────────────────────────────────────

def test_untouched_switch_reports_the_environment_default():
    service = MazdaModeService(InMemoryMazdaModeStore(), default_mode=SEMI_AUTOMATIC)
    state = service.current()
    assert state.mode == SEMI_AUTOMATIC
    assert state.source == 'default'


def test_default_is_read_live_not_captured():
    """server.py passes EXECUTION_MODE as a callable on purpose, so the env var
    stays the live default and the test suite's monkeypatch of it keeps
    working."""
    box = {'mode': AUTOMATIC}
    service = MazdaModeService(InMemoryMazdaModeStore(),
                               default_mode=lambda: box['mode'])
    assert service.mode() == AUTOMATIC
    box['mode'] = SEMI_AUTOMATIC
    assert service.mode() == SEMI_AUTOMATIC


def test_an_operator_choice_beats_the_default():
    service = MazdaModeService(InMemoryMazdaModeStore(), default_mode=SEMI_AUTOMATIC)
    state = service.set(MazdaModeRequest(automatic=True))
    assert state.mode == AUTOMATIC
    assert state.source == 'operator'
    assert service.current().source == 'operator'


def test_a_nonsense_default_falls_back_to_automatic():
    """A typo'd env var is caught at process start by resolve_execution_mode.
    If one ever reaches here anyway, the service must still answer with a real
    mode rather than blowing up the intake pipeline over a preference."""
    service = MazdaModeService(InMemoryMazdaModeStore(), default_mode='Auto')
    assert service.mode() == AUTOMATIC


def test_set_from_http_reports_the_reason_instead_of_raising():
    service = MazdaModeService(InMemoryMazdaModeStore(), default_mode=AUTOMATIC)
    out = service.set_from_http('nope')
    assert out['ok'] is False
    assert out['error']
    # ... and the switch did NOT move.
    assert service.mode() == AUTOMATIC


# ── the store ──────────────────────────────────────────────────────────────

def test_file_store_round_trips(tmp_path):
    store = JsonFileMazdaModeStore(str(tmp_path / 'nested' / 'mode.json'))
    assert store.read() is None
    store.write(SEMI_AUTOMATIC)
    assert store.read() == SEMI_AUTOMATIC


def test_file_store_survives_a_restart(tmp_path):
    path = str(tmp_path / 'mode.json')
    JsonFileMazdaModeStore(path).write(SEMI_AUTOMATIC)
    service = MazdaModeService(JsonFileMazdaModeStore(path),
                               default_mode=AUTOMATIC)
    assert service.mode() == SEMI_AUTOMATIC
    assert service.current().source == 'operator'


@pytest.mark.parametrize('content', ['', 'not json', '{"mode": "sideways"}', '[]'])
def test_a_corrupt_store_hands_control_back_to_the_default(tmp_path, content):
    """Unreadable means "nobody has chosen", never "turn Mazda on". A corrupt
    preferences file must not be able to start paid work by itself."""
    path = tmp_path / 'mode.json'
    path.write_text(content, encoding='utf-8')
    service = MazdaModeService(JsonFileMazdaModeStore(str(path)),
                               default_mode=SEMI_AUTOMATIC)
    assert service.mode() == SEMI_AUTOMATIC
    assert service.current().source == 'default'


def test_file_store_refuses_to_write_an_unknown_mode(tmp_path):
    store = JsonFileMazdaModeStore(str(tmp_path / 'mode.json'))
    with pytest.raises(ValueError):
        store.write('automatic')


def test_write_is_atomic_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / 'mode.json'
    JsonFileMazdaModeStore(str(path)).write(AUTOMATIC)
    assert json.loads(path.read_text(encoding='utf-8')) == {'mode': AUTOMATIC}
    assert [p.name for p in tmp_path.iterdir()] == ['mode.json']


# ── the switch and the dispatch fork are the same value ────────────────────

def test_switch_moves_the_dispatch_fork(monkeypatch):
    """The one assertion that matters: what the API says and what
    _dispatch_mazda_or_block reads are the same thing."""
    import server
    service = MazdaModeService(InMemoryMazdaModeStore(),
                               default_mode=lambda: server.EXECUTION_MODE)
    monkeypatch.setattr(server, '_MAZDA_MODE_SERVICE', service)
    monkeypatch.setattr(server, 'EXECUTION_MODE', 'auto')

    assert server.current_execution_mode() == AUTOMATIC
    service.set_from_http({'automatic': False})
    assert server.current_execution_mode() == SEMI_AUTOMATIC
    service.set_from_http({'automatic': True})
    assert server.current_execution_mode() == AUTOMATIC


# test_dispatch_is_blocked_only_while_semi_automatic moved to
# tests/test_mazda_dispatch.py with the fork itself: it monkeypatched
# server._block_dispatch_for_human_only_mode, a name the moved code never reads.


# ── cross-language parity ──────────────────────────────────────────────────

def test_javascript_labels_match_python():
    """The switch's text is rendered by Python into the mount point AND by the
    browser as the operator clicks. Two copies of a user-facing string that can
    drift is exactly how a control ends up lying about its own state."""
    source = open(MODE_INTERFACE_JS, encoding='utf-8').read()
    block = re.search(r'MAZDA_MODE_LABELS = Object\.freeze\(\{(.*?)\}\)',
                      source, re.S)
    assert block, 'MAZDA_MODE_LABELS not found in mazda-mode.interface.js'
    js_labels = set(re.findall(r'"([^"]+)"', block.group(1)))
    from intake.mazda_mode import MAZDA_MODE_LABELS
    assert js_labels == set(MAZDA_MODE_LABELS.values())


def test_javascript_mode_values_match_python():
    source = open(MODE_INTERFACE_JS, encoding='utf-8').read()
    block = re.search(r'MAZDA_MODE = Object\.freeze\(\{(.*?)\}\)', source, re.S)
    assert block
    js_modes = set(re.findall(r'"([^"]+)"', block.group(1)))
    assert js_modes == {AUTOMATIC, SEMI_AUTOMATIC}


# ── one gate, both document kinds ─────────────────────────────────────────

def test_only_one_place_decides_whether_mazda_runs():
    """Scans and PDFs must not be able to drift apart.

    Both entry points call server._dispatch_mazda_or_block, which is a thin
    wrapper over the one comparison in intake/mazda_dispatch.py. A second gate
    comparing the module-level EXECUTION_MODE would still be resolved at
    process start, so the switch would appear to work while one kind of
    document quietly ignored it.
    """
    import inspect

    import intake.mazda_dispatch as dispatch_mod
    import server

    fork = inspect.getsource(dispatch_mod)
    assert fork.count('current_mode() ==') == 1

    source = inspect.getsource(server)
    # server.py may read the constant as the DEFAULT (a lambda handed to the
    # service), never compare it directly to decide a dispatch.
    assert "EXECUTION_MODE == 'human_only'" not in source
    assert "EXECUTION_MODE == 'auto'" not in source
    assert 'current_execution_mode() ==' not in source
    assert source.count('_dispatch_mazda_or_block(') >= 3  # def + scan + pdf


# ── the env var behind the switch ──────────────────────────────────────────
# Moved here from tests/test_server.py with resolve_execution_mode itself: the
# env var and the operator's switch answer the same question with the same two
# words, and they used to spell that vocabulary out in separate files.

def test_the_vocabulary_has_exactly_one_definition():
    """AUTOMATIC/SEMI_AUTOMATIC, the MazdaMode alias every model annotates
    against, and MAZDA_MODE_LABELS' keys are three views of one pair. Before
    round 11 there was a fourth -- a Literal spelled out again in server.py's
    ExecutionModeConfig -- which is how a third mode gets added in one place
    and silently rejected in another."""
    from typing import get_args
    assert get_args(MazdaMode) == (AUTOMATIC, SEMI_AUTOMATIC)
    assert set(get_args(MazdaMode)) == set(MAZDA_MODE_LABELS)
    assert get_args(MazdaModeState.model_fields['mode'].annotation) == get_args(MazdaMode)
    assert get_args(ExecutionModeConfig.model_fields['mode'].annotation) == get_args(MazdaMode)


def test_resolve_execution_mode_unset_defaults_to_auto(monkeypatch):
    monkeypatch.delenv('MAZDA_DECISION_MODE', raising=False)
    assert resolve_execution_mode() == AUTOMATIC


def test_resolve_execution_mode_parses_auto_and_human_only():
    assert resolve_execution_mode('auto') == AUTOMATIC
    assert resolve_execution_mode('human_only') == SEMI_AUTOMATIC


@pytest.mark.parametrize('bad', [
    'Auto', 'HUMAN_ONLY', 'human-only', 'humanonly', 'llm_only', '',
    ' auto', 'auto ', 'None', None.__class__, 1, True,
])
def test_resolve_execution_mode_fails_closed_on_invalid_value(bad):
    """A typo must never silently fall back to 'auto' (could spend tokens
    unexpectedly) or silently disable Mazda — it must fail startup instead."""
    with pytest.raises(InvalidExecutionMode):
        resolve_execution_mode(bad)


def test_the_refusal_names_the_variable_and_shows_what_it_held():
    """It is read out of a systemd unit at 3am. "invalid mode" would not be."""
    with pytest.raises(InvalidExecutionMode) as exc:
        resolve_execution_mode('Human_Only')
    assert 'MAZDA_DECISION_MODE' in str(exc.value)
    assert "'Human_Only'" in str(exc.value)


def test_the_env_var_is_read_only_when_no_value_is_handed_in(monkeypatch):
    monkeypatch.setenv('MAZDA_DECISION_MODE', 'human_only')
    assert resolve_execution_mode() == SEMI_AUTOMATIC
    assert resolve_execution_mode('auto') == AUTOMATIC
