"""The dashboard's hand-off to the finance application's intake workflow."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from intake import finance_workflow_dispatch as fwd
from intake import intake_engine
from intake.mazda_dispatch import Collaborators, dispatch_or_block

DASHBOARD = Path(__file__).resolve().parents[1]


class Runner(fwd.IFinanceWorkflowRunner):
    def __init__(self, outcome='stored', problems=(), review_id=None, none=False):
        self.result = None if none else fwd.FinanceWorkflowResult(
            run_id='r1', outcome=outcome, problems=tuple(problems), review_id=review_id)
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return self.result


class Bench:
    def __init__(self, engine=intake_engine.FINANCE_WORKFLOW, **runner):
        self.engine, self.runner = engine, Runner(**runner)
        self.merged, self.earlier = [], []
        self.dispatcher = fwd.FinanceWorkflowDispatcher(
            engine=lambda: self.engine, runner=self.runner,
            merge_status=self.merged.append, start=lambda work: work())

    def dispatch(self, facade=None, conversation_id='conv-1', dispatched_at=100.5):
        return self.dispatcher.dispatch(
            '/scans/a.jpg', 'Freezer Scanner', facade or {'doc_kind': 'unknown'},
            conversation_id, dispatched_at, lambda: self.earlier.append(True))


def test_the_default_engine_leaves_everything_as_it_was(monkeypatch, tmp_path):
    monkeypatch.delenv('FINANCE_INTAKE_ENGINE', raising=False)
    service = intake_engine.IntakeEngineService(str(tmp_path / 'engine.json'))
    assert service.current() == 'mazda_agent'
    bench = Bench(engine=service.current())
    assert bench.dispatch() is False and bench.runner.requests == []


def test_the_engine_file_switches_without_a_restart_and_survives_one(tmp_path):
    path = str(tmp_path / 'engine.json')
    service = intake_engine.IntakeEngineService(path, default=lambda: 'mazda_agent')
    service.set('finance_workflow')
    assert intake_engine.IntakeEngineService(path, default=lambda: 'mazda_agent').current() == 'finance_workflow'
    service.set('mazda_agent')
    assert service.current() == 'mazda_agent'


@pytest.mark.parametrize('content', ['not json', '{"engine": "turbo"}', '[]', ''])
def test_a_bad_engine_file_never_selects_the_new_engine(tmp_path, content):
    path = tmp_path / 'engine.json'
    path.write_text(content)
    assert intake_engine.IntakeEngineService(str(path), default=lambda: 'mazda_agent').current() == 'mazda_agent'


def test_a_typo_in_the_environment_fails_closed():
    with pytest.raises(intake_engine.InvalidIntakeEngine):
        intake_engine.resolve_intake_engine('Finance_Workflow')
    with pytest.raises(intake_engine.InvalidIntakeEngine):
        intake_engine.IntakeEngineService('/nonexistent/x.json').set('turbo')


def test_a_stored_receipt_needs_no_status_from_here():
    bench = Bench(outcome='stored')
    assert bench.dispatch() is True
    assert bench.merged == [] and bench.earlier == []
    request = bench.runner.requests[0]
    assert (request.conversation_id, request.dispatched_at) == ('conv-1', 100.5)


@pytest.mark.parametrize('outcome,status', [
    ('needs_human_review', 'needs_human_review'), ('awaiting_vendor_review', 'awaiting_vendor_review'),
    ('failed', 'fail'), ('halted', 'fail'), ('not_financial', 'complete')])
def test_a_run_that_did_not_store_tells_the_scanner_tab_why(outcome, status):
    bench = Bench(outcome=outcome, problems=('a probable duplicate could not be settled',),
                  review_id='abcdef1234567890')
    bench.dispatch()
    (update,) = bench.merged
    assert update['status'] == status and update['status_source'] == 'finance_workflow'
    assert update['conversation_id'] == 'conv-1' and update['document_path'] == '/scans/a.jpg'
    assert 'probable duplicate' in update['status_detail'] and 'abcdef12' in update['status_detail']
    assert bench.earlier == []


def test_only_unsupported_falls_back_to_the_earlier_path():
    bench = Bench(outcome='unsupported', problems=('statement is not yet handled',))
    assert bench.dispatch() is True
    assert bench.earlier == [True] and bench.merged == []


def test_a_run_with_no_result_is_a_failure_and_is_never_retried_elsewhere():
    bench = Bench(none=True)
    bench.dispatch()
    assert bench.earlier == [] and bench.merged[0]['status'] == 'fail'
    assert 'Nothing was retried' in bench.merged[0]['status_detail']


@pytest.mark.parametrize('facade', [
    {'doc_kind': 'statement'}, {'doc_kind': 'bank_statement'},
    {'doc_kind': 'unknown', 'statement_preflight': {'bank_name': 'Chase'}}])
def test_statements_stay_on_the_earlier_path_for_now(facade):
    bench = Bench()
    assert bench.dispatch(facade=facade) is False and bench.runner.requests == []


@pytest.mark.parametrize('kwargs', [{'conversation_id': ''}, {'dispatched_at': 0}])
def test_a_document_without_an_identity_is_not_taken(kwargs):
    bench = Bench()
    assert bench.dispatch(**kwargs) is False and bench.runner.requests == []


def test_a_malformed_result_file_reads_as_no_result():
    assert fwd.FinanceWorkflowResult.from_json('{"outcome": "stored"}') is None
    assert fwd.FinanceWorkflowResult.from_json('garbage') is None
    good = fwd.FinanceWorkflowResult.from_json(json.dumps(
        {'run_id': 'r', 'outcome': 'stored', 'amount': '4.00', 'problems': []}))
    assert good.outcome == 'stored'


# -- The fork itself -----------------------------------------------------------

class Fork:
    def __init__(self, mode='auto', takes=True):
        self.mode, self.takes = mode, takes
        self.watched, self.merged, self.workflow, self.threads = [], [], [], []

    def deps(self):
        def workflow(*args):
            self.workflow.append(args)
            return self.takes
        return Collaborators(
            current_mode=lambda: self.mode, watch_intake=lambda *a: self.watched.append(a),
            merge_status=lambda u: self.merged.append(u) or True,
            observe_callback=lambda p: None, letta_get=lambda *a, **k: None,
            finance_workflow=workflow)

    def run(self, monkeypatch):
        import intake.mazda_dispatch as md

        class Thread:
            def __init__(inner, **kwargs):
                self.threads.append(kwargs)

            def start(inner):
                return None
        monkeypatch.setattr(md.threading, 'Thread', Thread)
        return dispatch_or_block(self.deps(), '/scans/a.jpg', 'Freezer Scanner', {},
                                 'conv-1', 100.5, lambda: None, ())


def test_semi_automatic_still_wins_over_any_engine(monkeypatch):
    fork = Fork(mode='human_only')
    assert fork.run(monkeypatch) is False
    assert fork.workflow == [] and fork.threads == [] and fork.merged[0]['status'] == 'needs_human_review'


def test_a_document_the_workflow_takes_starts_no_agent_turn_and_no_trainer_watch(monkeypatch):
    fork = Fork(takes=True)
    assert fork.run(monkeypatch) is True
    assert len(fork.workflow) == 1 and fork.watched == [] and fork.threads == []


def test_a_document_the_workflow_declines_goes_exactly_the_earlier_way(monkeypatch):
    fork = Fork(takes=False)
    assert fork.run(monkeypatch) is True
    assert len(fork.watched) == 1 and len(fork.threads) == 1


def test_the_fallback_handed_to_the_workflow_is_the_earlier_path(monkeypatch):
    fork = Fork(takes=True)
    fork.run(monkeypatch)
    fork.workflow[0][-1]()          # what an "unsupported" run would call
    assert len(fork.watched) == 1 and len(fork.threads) == 1


# -- Boundary: the dashboard hands off; it does not reach in -------------------

def imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or '')
    return found


@pytest.mark.parametrize('name', ['finance_workflow_dispatch.py', 'intake_engine.py'])
def test_the_hand_off_imports_no_model_client_and_no_finance_code(name):
    banned = ('finance_app', 'architecture', 'letta', 'letta_client', 'anthropic', 'openai',
              'google', 'urllib', 'hosts', 'mazda_service', 'mazda_receptionist_service',
              'intake.scan_message', 'pymysql')
    found = imports(DASHBOARD / 'intake' / name)
    bad = sorted(m for m in found if any(m == b or m.startswith(b + '.') for b in banned))
    assert bad == []


def test_no_browser_code_addresses_mazda_or_letta_directly_for_intake():
    """UI -> Mazda bypass check: the scanner and intake front end talk to the
    dashboard's own /api routes only."""
    offenders = []
    for path in (DASHBOARD / 'js').rglob('*.js'):
        if 'tests' in path.parts or 'adw-debugger' in path.parts:
            continue
        name = path.name.lower()
        if not any(word in name for word in ('scanner', 'intake', 'receipt', 'expense', 'statement')):
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        if ':8283' in text or '/v1/conversations' in text or '/v1/agents' in text:
            offenders.append(str(path.relative_to(DASHBOARD)))
    assert offenders == []
