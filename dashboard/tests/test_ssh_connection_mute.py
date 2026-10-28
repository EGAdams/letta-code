import ssh_connection_mute as scm
import pytest
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _isolate_mute_file(tmp_path, monkeypatch):
    monkeypatch.setattr(scm, 'SSH_CONNECTION_MUTE_FILE', str(tmp_path / 'ssh_connection_muted.json'))


def test_unmuted_by_default():
    assert scm.is_muted('chromebook-a13') is False


def test_set_muted_persists():
    assert scm.set_muted('chromebook-a13', True) is True
    assert scm.is_muted('chromebook-a13') is True
    assert scm.is_muted('win11') is False  # other connections unaffected


def test_set_muted_false_clears():
    scm.set_muted('chromebook-a13', True)
    assert scm.set_muted('chromebook-a13', False) is False
    assert scm.is_muted('chromebook-a13') is False


def test_apply_mute_overlay_downgrades_down_to_up_while_muted():
    scm.set_muted('chromebook-a13', True)
    out = scm.apply_mute_overlay({'key': 'chromebook-a13', 'name': 'ChromeBook A13', 'status': 'down'},
                                  'chromebook-a13')
    assert out == {'key': 'chromebook-a13', 'name': 'ChromeBook A13', 'status': 'up',
                   'muted': True, 'raw_status': 'down'}


def test_apply_mute_overlay_leaves_unmuted_status_untouched():
    out = scm.apply_mute_overlay({'key': 'chromebook-a13', 'status': 'down'}, 'chromebook-a13')
    assert out == {'key': 'chromebook-a13', 'status': 'down', 'muted': False}


def test_apply_mute_overlay_does_not_mutate_input():
    original = {'status': 'down'}
    scm.set_muted('chromebook-a13', True)
    scm.apply_mute_overlay(original, 'chromebook-a13')
    assert original == {'status': 'down'}  # overlay returns a copy


def test_mute_request_fails_closed_on_unknown_fields():
    with pytest.raises(ValidationError):
        scm.SshConnectionMuteRequest.model_validate({'key': 'chromebook-a13', 'muted': True, 'extra': 1})


def test_mute_request_requires_bool_muted():
    with pytest.raises(ValidationError):
        scm.SshConnectionMuteRequest.model_validate({'key': 'chromebook-a13', 'muted': 'yes'})
