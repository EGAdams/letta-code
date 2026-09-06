"""Mazda's tool reconciliation check.

The bug this file exists to prevent is a diagnosis, not a crash. Letta's
``/v1/agents/{id}/tools`` endpoint pages at 10; a check that read one page
reported a fully-stocked 19-tool agent as "9 of 15 attached, 6 missing", and
that phantom gap was chased and "fixed" before anyone noticed the page size.
A wrong green light wastes an afternoon; a wrong red light wastes a day.

So the paging test below is the important one, and the fake deliberately pages
at a size smaller than the tool set. The rest pin the three verdicts apart:
missing (the agent cannot call its own tools), stale (it carries tools the
server dropped), and agreed.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from health import mazda_tools


def _tool(name, server=mazda_tools.MCP_SERVER_NAME):
    """One row shaped like Letta's, including the provenance metadata."""
    row = {'name': name, 'id': f'tool-{name}', 'tool_type': 'custom'}
    if server:
        row['tool_type'] = 'external_mcp'
        row['metadata_'] = {'mcp': {'server_name': server}}
    return row


class FakeLetta:
    """Serves the two endpoints reconcile() reads, with real pagination."""

    def __init__(self, served, attached, page_size=10):
        self.served = list(served)
        self.attached = list(attached)
        self.page_size = page_size

    def get(self, url):
        if url.endswith('/tools') and '/mcp/servers/' in url:
            return [{'name': n} for n in self.served]
        # Agent tools: honour limit/after the way Letta does.
        after = None
        if 'after=' in url:
            after = url.split('after=')[1].split('&')[0]
        rows = self.attached
        if after is not None:
            index = next(i for i, r in enumerate(rows) if r['id'] == after)
            rows = rows[index + 1:]
        return rows[:self.page_size]


@pytest.fixture
def patch_http(monkeypatch):
    def install(fake):
        monkeypatch.setattr(mazda_tools, '_get_json', fake.get)
        return fake
    return install


def test_pages_past_the_default_limit(patch_http):
    """A 15-tool agent behind a 10-row page is in sync, not 5 short.

    This is the exact shape of the false alarm that motivated the module.
    """
    names = [f'tool_{i:02d}' for i in range(15)]
    patch_http(FakeLetta(served=names, attached=[_tool(n) for n in names],
                         page_size=10))

    report = mazda_tools.reconcile()

    assert report['missing'] == []
    assert report['ok'] is True
    assert len(report['attached']) == 15


def test_missing_tools_are_named_and_not_ok(patch_http):
    served = ['record_trace', 'judge_trace', 'gate_check']
    patch_http(FakeLetta(served=served, attached=[_tool('judge_trace')]))

    report = mazda_tools.reconcile()

    assert report['ok'] is False
    assert report['missing'] == ['gate_check', 'record_trace']
    assert 'record_trace' in report['text']
    # The operator is told what to run, in the report itself.
    assert 'letta_tools.registry' in report['remediation']


def test_tools_from_other_mcp_servers_are_not_stale(patch_http):
    """`executor_run` lives on executor_server. It is not Mazda's problem.

    The first draft of this check flagged it as stale and turned a healthy
    system yellow.
    """
    patch_http(FakeLetta(
        served=['record_trace'],
        attached=[_tool('record_trace'),
                  _tool('executor_run', server='executor_server'),
                  _tool('run_claude_code_sdk', server=None)],
    ))

    report = mazda_tools.reconcile()

    assert report['ok'] is True
    assert report['stale'] == []
    assert report['other_attached'] == ['executor_run', 'run_claude_code_sdk']


def test_tool_dropped_from_the_server_is_stale_and_a_concern(patch_http):
    patch_http(FakeLetta(
        served=['record_trace'],
        attached=[_tool('record_trace'), _tool('retired_tool')],
    ))

    report = mazda_tools.reconcile()

    assert report['stale'] == ['retired_tool']
    # Reachable and callable for everything current: a concern, not an outage.
    assert report['ok'] is True
    assert report['concern'] is True


def test_missing_outranks_stale(patch_http):
    patch_http(FakeLetta(
        served=['record_trace', 'judge_trace'],
        attached=[_tool('record_trace'), _tool('retired_tool')],
    ))

    report = mazda_tools.reconcile()

    assert report['ok'] is False
    assert report['missing'] == ['judge_trace']


def test_unreachable_letta_is_hard_down_not_a_false_gap(monkeypatch):
    """A dead server must never render as "15 tools missing"."""
    def boom(url):
        raise OSError('connection refused')
    monkeypatch.setattr(mazda_tools, '_get_json', boom)

    report = mazda_tools.reconcile()

    assert report['ok'] is False
    assert report['hard'] is True
    assert report['reachable'] is False
    assert report['missing'] == []
    assert 'connection refused' in report['text']


def test_payload_is_json_serialisable(patch_http):
    patch_http(FakeLetta(served=['record_trace'],
                         attached=[_tool('record_trace')]))
    json.dumps(mazda_tools.reconcile())
