"""nav_status.nav_signature_payload — the signature DomNavLiveSync polls for.

It must change when the sidebar markup changes and stay stable otherwise, with
no dependency on anything but the file currently on disk.
"""
from http_app import nav_status


def test_signature_is_stable_for_unchanged_markup():
    first = nav_status.nav_signature_payload()
    second = nav_status.nav_signature_payload()
    assert first == second
    assert isinstance(first['signature'], str) and first['signature']


def test_signature_changes_when_nav_main_markup_changes(monkeypatch):
    monkeypatch.setattr(
        nav_status, '_nav_main_markup', lambda: '<nav id="nav-main">A</nav>')
    a = nav_status.nav_signature_payload()
    monkeypatch.setattr(
        nav_status, '_nav_main_markup', lambda: '<nav id="nav-main">B</nav>')
    b = nav_status.nav_signature_payload()
    assert a['signature'] != b['signature']


def test_signature_ignores_markup_outside_nav_main():
    html_a = '<nav id="nav-main"><button>X</button></nav><p>one</p>'
    html_b = '<nav id="nav-main"><button>X</button></nav><p>two</p>'
    extract = nav_status._NAV_MAIN_RE.search
    assert extract(html_a).group(0) == extract(html_b).group(0)


def test_missing_file_yields_a_stable_empty_signature(monkeypatch, tmp_path):
    monkeypatch.setattr(nav_status, 'DASHBOARD_HTML', str(tmp_path / 'missing.html'))
    payload = nav_status.nav_signature_payload()
    assert payload == nav_status.nav_signature_payload()
