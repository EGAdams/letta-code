from pathlib import Path


DASHBOARD_DIR = Path(__file__).resolve().parents[1]


def test_dashboard_loads_the_last_scan_controls_stylesheet():
    html = (DASHBOARD_DIR / "dashboard.html").read_text()

    assert '/css/scanner-report-controls.css?v=20260903' in html


def test_last_scan_dialogs_receive_the_extra_report_height():
    css = (DASHBOARD_DIR / "css" / "scanner-report-controls.css").read_text()

    assert "#scanners-last-window .plan-frame" in css
    assert "#scanners-last-freezer .plan-frame" in css
    assert "height: calc(100vh - 60px + 20vh)" in css
