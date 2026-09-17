"""Explaining a failing/review report.html to a human on the dashboard.

The dashboard iframe hides everything except Verified Transactions, so the
parent view needs the hero badge, summary, unresolved sections, and the
report author's required/recommended next action pulled back out of the HTML.

``server.py`` still owns ``REPORT_VERDICT_SOURCE`` (rebuilt/rebound by tests,
including the autouse ``NullReportVerdictSource`` fixture in conftest.py), so
the caller resolves the default there and always hands this module a concrete
source -- never ``None``.
"""

from __future__ import annotations

import re


def _strip_html_text(fragment):
    """Collapse an HTML fragment to its visible text (tags dropped,
    whitespace normalized)."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', fragment)).strip()


def auditor_attention_detail(report_file, verdict_source):
    """The explanation for a report the auditor overruled.

    A report failed by the auditor while still claiming PASS inside has no
    explanation of its own to show — the red tab would otherwise say only "this
    needs attention". These lines are the auditor's actual findings, e.g.
    "beginning_balance 51,105.41 does not appear in <its own PDF>". Returns None
    when the auditor has no complaint.
    """
    if verdict_source.verdict(report_file) != 'fail':
        return None
    findings = verdict_source.findings(report_file)
    return {
        'badge': 'FAILED VERIFICATION',
        'summary': ('The report claims to pass, but checking it against the '
                    'source document in its own folder contradicts it.'),
        'issues': [{'section': 'Source document check', 'status': 'FAIL', 'text': f}
                   for f in findings],
        'recommended_action': ('Re-parse the source PDF in this folder and '
                               'regenerate the report from it; do not patch the '
                               'generated HTML.'),
    }


def extract_report_attention_detail(report_file, verdict_source):
    """Pull the human-facing explanation out of a fail/review report.html.

    Returns a detail dict or None when the report has no recognizable
    attention information.

    When the auditor overruled the report's own badge, its findings lead —
    whatever a contradicted report says about itself is not the explanation the
    reader needs.
    """
    overruled = auditor_attention_detail(report_file, verdict_source)
    if overruled:
        return overruled
    try:
        with open(report_file, 'r', encoding='utf-8', errors='replace') as f:
            html = f.read()
    except OSError:
        return None
    detail = {}
    m = re.search(r'<div class="badge[^"]*">(.*?)</div>', html, re.S)
    if m:
        detail['badge'] = _strip_html_text(m.group(1))
    m = re.search(r'<div class="summary-box">(.*?)</div>', html, re.S)
    if m:
        detail['summary'] = _strip_html_text(m.group(1))
    # Older reports use a flat <h2> + <p class="warn"> layout instead of
    # hero/card wrappers. Their final-status paragraph is both the badge and
    # the best available summary.
    if not detail.get('badge'):
        m = re.search(
            r'<h2[^>]*>Final[^<]*Status</h2>\s*<p[^>]*class=["\'](?:warn|fail)["\'][^>]*>(.*?)</p>',
            html,
            re.S | re.I,
        )
        if m:
            final_text = _strip_html_text(m.group(1))
            detail['badge'] = final_text
            detail.setdefault('summary', final_text)
    issues = []
    for sec in re.finditer(r'<section class="card">(.*?)</section>', html, re.S):
        body = sec.group(1)
        sm = re.search(r'<span class="status-(fail|warn)[^"]*">(.*?)</span>',
                       body, re.S)
        if not sm:
            continue
        hm = re.search(r'<h2[^>]*>(.*?)</h2>', body, re.S)
        # First paragraph of the section, with the status pill itself removed
        # so its label isn't duplicated in the text.
        pm = re.search(r'<p>(.*?)</p>', body, re.S)
        text = ''
        if pm:
            text = _strip_html_text(
                re.sub(r'<span class="status-[^"]*">.*?</span>', '', pm.group(1), flags=re.S))
        issues.append({
            'section': _strip_html_text(hm.group(1)) if hm else '',
            'status': _strip_html_text(sm.group(2)),
            'text': text,
        })
    if issues:
        detail['issues'] = issues
    else:
        # Legacy flat reports put each warning immediately after its heading.
        for sec in re.finditer(
            r'<h2[^>]*>([^<]+)</h2>\s*<p[^>]*class=["\'](warn|fail)["\'][^>]*>(.*?)</p>',
            html,
            re.S | re.I,
        ):
            section = _strip_html_text(sec.group(1))
            if section.lower().startswith('final '):
                continue
            raw_text = _strip_html_text(sec.group(3))
            status_match = re.match(r'([A-Z_ ]+)\s*[—-]\s*(.*)', raw_text)
            issues.append({
                'section': section,
                'status': (status_match.group(1).replace('_', ' ').strip()
                           if status_match else sec.group(2).upper()),
                'text': status_match.group(2).strip() if status_match else raw_text,
            })
        if issues:
            detail['issues'] = issues
    for paragraph in re.finditer(r'<p[^>]*>(.*?)</p>', html, re.S):
        paragraph_text = _strip_html_text(paragraph.group(1))
        action = re.match(
            r'(?:Required|Recommended) next actions?\s*:\s*(.+)',
            paragraph_text,
            re.I,
        )
        if action:
            detail['recommended_action'] = action.group(1).strip()
            break
    return detail or None
