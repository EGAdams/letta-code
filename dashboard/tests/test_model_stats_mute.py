import model_stats_mute as msm
import pytest
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _isolate_mute_file(tmp_path, monkeypatch):
    monkeypatch.setattr(msm, 'MODEL_STATS_MUTE_FILE', str(tmp_path / 'model_stats_muted.json'))


def test_unmuted_by_default():
    assert msm.is_muted('r46-codex') is False


def test_set_muted_persists():
    assert msm.set_muted('r46-codex', True) is True
    assert msm.is_muted('r46-codex') is True
    assert msm.is_muted('w11-codex') is False  # other sources unaffected


def test_set_muted_false_clears():
    msm.set_muted('r46-codex', True)
    assert msm.set_muted('r46-codex', False) is False
    assert msm.is_muted('r46-codex') is False


def test_apply_mute_overlay_downgrades_concern_to_up_while_muted():
    msm.set_muted('r46-codex', True)
    out = msm.apply_mute_overlay({'status': 'down', 'detail': 'maxed out'}, 'r46-codex')
    assert out == {'status': 'up', 'detail': 'maxed out', 'muted': True, 'raw_status': 'down'}


def test_apply_mute_overlay_leaves_unmuted_status_untouched():
    out = msm.apply_mute_overlay({'status': 'concern', 'detail': 'x'}, 'r46-codex')
    assert out == {'status': 'concern', 'detail': 'x', 'muted': False}


def test_apply_mute_overlay_does_not_mutate_input():
    original = {'status': 'down'}
    msm.set_muted('r46-codex', True)
    msm.apply_mute_overlay(original, 'r46-codex')
    assert original == {'status': 'down'}  # overlay returns a copy


def test_mute_request_fails_closed_on_unknown_fields():
    with pytest.raises(ValidationError):
        msm.ModelStatsMuteRequest.model_validate({'source': 'r46-codex', 'muted': True, 'extra': 1})


def test_mute_request_requires_bool_muted():
    with pytest.raises(ValidationError):
        msm.ModelStatsMuteRequest.model_validate({'source': 'r46-codex', 'muted': 'yes'})
