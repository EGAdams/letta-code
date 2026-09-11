"""Auto-recover behavior for the Codex fallback-token sync panel.

Covers the 2026-09-11 fix: the fallback slot silently held EG's own account
for weeks because the only refresh was a 4h timer that had been left
disabled. `codex_sync_status()` now self-heals a collapsed slot on every
read (unless the collapse was a deliberate 'Copy from W11'), and reports
`needs_reauth` when even that resync doesn't fix it.
"""

import json

import codex_sync_status as css


def _write_auth_json(path, email):
    path.write_text(json.dumps({
        'tokens': {'access_token': f'x.{_b64_profile(email)}.y'},
    }))


def _b64_profile(email):
    import base64
    payload = json.dumps({'https://api.openai.com/profile': {'email': email}})
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')


class FakeSyncSource:
    def __init__(self, ok, fixed_email=None, moms_path=None):
        self._ok = ok
        self._fixed_email = fixed_email
        self._moms_path = moms_path

    def sync(self):
        if self._ok and self._fixed_email and self._moms_path:
            _write_auth_json(self._moms_path, self._fixed_email)
        return self._ok, 'fake sync'


def _patch_paths(monkeypatch, tmp_path, primary_email, moms_email):
    primary = tmp_path / 'primary_auth.json'
    moms = tmp_path / 'moms_auth.json'
    last_source = tmp_path / 'last_sync_source'
    if primary_email is not None:
        _write_auth_json(primary, primary_email)
    if moms_email is not None:
        _write_auth_json(moms, moms_email)
    monkeypatch.setattr(css, 'CODEX_PRIMARY_AUTH_JSON', str(primary))
    monkeypatch.setattr(css, 'CODEX_MOMS_AUTH_JSON', str(moms))
    monkeypatch.setattr(css, 'CODEX_MOMS_LAST_SOURCE_FILE', str(last_source))
    monkeypatch.setattr(css, '_last_auto_recover_attempt_epoch', None)
    return primary, moms


def test_not_collapsed_no_recovery_attempted(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path, 'eg1972@gmail.com', 'rbarnesrol@aol.com')
    monkeypatch.setitem(css.SYNC_SOURCES, 'r46', FakeSyncSource(ok=False))
    status = css.codex_sync_status()
    assert status.needs_reauth is False
    assert status.slots[1].email == 'rbarnesrol@aol.com'


def test_collapsed_slot_self_heals(monkeypatch, tmp_path):
    _primary, moms = _patch_paths(monkeypatch, tmp_path, 'eg1972@gmail.com', 'eg1972@gmail.com')
    monkeypatch.setitem(
        css.SYNC_SOURCES, 'r46',
        FakeSyncSource(ok=True, fixed_email='rbarnesrol@aol.com', moms_path=moms),
    )
    status = css.codex_sync_status()
    assert status.needs_reauth is False
    assert status.slots[1].email == 'rbarnesrol@aol.com'


def test_collapsed_slot_stays_collapsed_reports_needs_reauth(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path, 'eg1972@gmail.com', 'eg1972@gmail.com')
    monkeypatch.setitem(css.SYNC_SOURCES, 'r46', FakeSyncSource(ok=False))
    status = css.codex_sync_status()
    assert status.needs_reauth is True
    assert status.reauth_message == css.REAUTH_MESSAGE


def test_deliberate_w11_collapse_is_left_alone(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path, 'eg1972@gmail.com', 'eg1972@gmail.com')
    css._record_last_source('w11')
    monkeypatch.setitem(css.SYNC_SOURCES, 'r46', FakeSyncSource(ok=True, fixed_email='should-not-be-used'))
    status = css.codex_sync_status()
    assert status.needs_reauth is False
    assert status.slots[1].email == 'eg1972@gmail.com'


def test_recovery_attempt_is_cooled_down(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path, 'eg1972@gmail.com', 'eg1972@gmail.com')
    fake = FakeSyncSource(ok=False)
    monkeypatch.setitem(css.SYNC_SOURCES, 'r46', fake)
    css.codex_sync_status()  # first call attempts and fails
    calls_after_first = []
    monkeypatch.setattr(fake, 'sync', lambda: calls_after_first.append(1) or (False, ''))
    status = css.codex_sync_status()  # second call within cooldown must not retry
    assert calls_after_first == []
    assert status.needs_reauth is True


def test_run_codex_sync_now_records_w11_source(monkeypatch, tmp_path):
    primary, moms = _patch_paths(monkeypatch, tmp_path, 'eg1972@gmail.com', 'rbarnesrol@aol.com')
    monkeypatch.setitem(
        css.SYNC_SOURCES, 'w11',
        FakeSyncSource(ok=True, fixed_email='eg1972@gmail.com', moms_path=moms),
    )
    css.run_codex_sync_now('w11')
    assert css._last_recorded_source() == 'w11'
