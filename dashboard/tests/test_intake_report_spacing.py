from pathlib import Path


DASHBOARD_DIR = Path(__file__).resolve().parents[1]


def test_intake_report_loads_focused_form_stylesheets():
    css = (DASHBOARD_DIR / "css" / "finance" / "intake_report.css").read_text()

    assert '@import url("./manual-entry.css?v=20260903")' in css
    assert '@import url("./mazda-mode.css?v=20260903")' in css


def test_manual_entry_uses_three_pixel_vertical_spacing_and_collapses_empty_rows():
    css = (DASHBOARD_DIR / "css" / "finance" / "manual-entry.css").read_text()

    assert "--manual-entry-block-space:3px" in css
    assert "margin:var(--manual-entry-block-space) 0" in css
    assert "padding:var(--manual-entry-block-space) 12px" in css
    assert ".manual-entry-errors:empty, .manual-entry-status:empty { display:none; }" in css
