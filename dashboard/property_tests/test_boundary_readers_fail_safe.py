"""Every boundary reader must fail SAFE, never optimistic.

Four defects on 2026-08-19 were one defect wearing four hats. In each, code
that reads data from outside itself answered the *convenient* thing when the
data was absent, garbled, or not the shape it expected:

* `_mazda_dispatch_was_accepted` counted any `in_context_message_ids` entry as
  proof the dispatch landed. A fresh conversation carries its system prompt, so
  it said "delivered" about a conversation nothing was ever posted to. A scan
  rejected with HTTP 429 was recorded as in-flight and hung.
* `DispatchEvidence` (written to fix that) turned a row that wasn't a mapping
  into a blank message, which is "not the system prompt", which counted as
  delivery. The same bug, in the fix for the bug.
* `MazdaModeRequest.from_http` used `bool(data.get('automatic'))`, so the
  string "maybe" -- or "false" -- switched paid reading ON and answered ok.
* Gemini's ladder reported whichever model failed *last*, so a run where the
  first model answered usefully was reported as a quota error.

The unit tests for each cover the cases someone thought of. This file covers
the ones nobody thought of: it takes every boundary reader in the intake path
and feeds it the same corpus of hostile values, asserting that not one of them
can be talked into the optimistic answer.

Adding a reader here is one line in READERS. That is deliberate -- the next
boundary reader gets this sweep for free, and the failure this file exists to
catch is precisely the one an author does not anticipate.
"""

import json

import pytest

from finance.manual_entry import preview_receipt_parse
from finance.mazda_fill import MazdaFillRequest
from finance.statement_models import (
    StatementBreakupRequest,
    StatementStoreRequest,
)
from finance.receipt_read_outcome import EngineFailure, ReceiptReadOutcome
from intake.dispatch_evidence import DispatchEvidence
from intake.mazda_mode import (
    AUTOMATIC,
    InMemoryMazdaModeStore,
    MazdaModeRequest,
    MazdaModeService,
    SEMI_AUTOMATIC,
)

#: Everything a boundary can hand us when something upstream has gone wrong: a
#: dead server, a truncated response, a schema change, a proxy returning HTML,
#: a field renamed, a value that arrived as text instead of JSON.
HOSTILE_INPUTS = [
    None,
    {},
    [],
    (),
    '',
    ' ',
    0,
    1,
    -1,
    True,
    False,
    0.0,
    'null',
    'true',
    'maybe',
    'ok',
    b'',
    b'{}',
    [None],
    [[]],
    [0],
    ['x'],
    [{'unexpected': 'shape'}],
    {'messages': None},
    {'messages': 'nope'},
    {'messages': {}},
    {'ok': True},
    {'ok': 'yes'},
    {'error': None},
    {'engine_failure': None},
    {'engine_failure': []},
    {'engine_failure': {'kind': None}},
    {'automatic': 'true'},
    {'automatic': 'false'},
    {'automatic': 1},
    {'automatic': []},
    {'in_context_message_ids': ['message-anything']},  # the 2026-08-19 premise
    '<html>502 Bad Gateway</html>',
    float('nan'),
    float('inf'),
]


def _mode_service_stays_put(value):
    """Did a hostile body move the switch to Automatic?

    Starts in Semi-Automatic, the mode that spends nothing. Any hostile input
    that lands on Automatic has switched paid reading on by accident.
    """
    service = MazdaModeService(InMemoryMazdaModeStore(SEMI_AUTOMATIC),
                               default_mode=SEMI_AUTOMATIC)
    try:
        service.set_from_http(value)
    except Exception:
        return False  # refusing outright is a safe answer
    return service.mode() == AUTOMATIC


def _mode_request_says_automatic(value):
    try:
        return MazdaModeRequest.from_http(value).mode == AUTOMATIC
    except Exception:
        return False


def _request_was_accepted(model):
    """A request built from junk runs a paid reader, or stores expenses, on
    whatever fields survived. Refusing is the only safe answer."""
    def verdict(value):
        try:
            model.from_http(value)
            return True
        except Exception:
            return False
    return verdict


def _a_junk_report_would_fill_the_form(value):
    """The whole receipt-preview boundary, not just one marker check.

    This is where a subprocess's output becomes fields in the operator's form.
    Whatever the reader hands back -- a schema change, a truncated report, an
    error page -- it must never come out as a filled-in expense.
    """
    ok, _payload = preview_receipt_parse(
        '/staged/x.jpg', engine='gemini-only',
        runner=lambda _cmd: {'returncode': 0, 'report': value, 'stderr': ''})
    return ok


#: (name, verdict, the answer that would be a lie)
#:
#: `verdict` returns the reader's optimistic claim as a bool. The sweep asserts
#: it never equals `unsafe` for any hostile input.
READERS = [
    (
        'DispatchEvidence.dispatch_landed',
        lambda v: DispatchEvidence.from_payload(v).dispatch_landed,
        True,
    ),
    (
        'ReceiptReadOutcome.ok',
        lambda v: ReceiptReadOutcome.from_reader(False, v).ok,
        True,
    ),
    (
        'ReceiptReadOutcome.warrants_statement_retry',
        lambda v: ReceiptReadOutcome.from_reader(False, v).warrants_statement_retry,
        True,
    ),
    (
        'EngineFailure.answered',
        lambda v: bool(getattr(EngineFailure.from_payload(v), 'answered', False)),
        True,
    ),
    ('MazdaModeService.set_from_http', _mode_service_stays_put, True),
    ('MazdaModeRequest.from_http', _mode_request_says_automatic, True),
    ('MazdaFillRequest.from_http', _request_was_accepted(MazdaFillRequest), True),
    ('StatementBreakupRequest.from_http',
     _request_was_accepted(StatementBreakupRequest), True),
    ('StatementStoreRequest.from_http',
     _request_was_accepted(StatementStoreRequest), True),
    ('preview_receipt_parse', _a_junk_report_would_fill_the_form, True),
]


@pytest.mark.parametrize('value', HOSTILE_INPUTS, ids=repr)
@pytest.mark.parametrize('name,verdict,unsafe', READERS, ids=lambda a: a if isinstance(a, str) else '')
def test_no_boundary_reader_can_be_talked_into_the_optimistic_answer(
        name, verdict, unsafe, value):
    assert verdict(value) is not unsafe, (
        f'{name} answered {unsafe!r} for {value!r}. That is the answer that '
        f'costs money or hides a failure; unreadable input must never produce it.')


@pytest.mark.parametrize('value', HOSTILE_INPUTS, ids=repr)
@pytest.mark.parametrize('name,verdict,unsafe', READERS, ids=lambda a: a if isinstance(a, str) else '')
def test_no_boundary_reader_raises_on_hostile_input(name, verdict, unsafe, value):
    """A reader that throws takes down the request that was going to report the
    real problem. Every one of these runs on an error path already."""
    verdict(value)


# ── premises about other systems, pinned to what they actually return ──────
# The dispatch defect was a docstring asserting something about Letta that was
# never true. A premise is only worth what the recorded evidence says, so the
# evidence lives here.

#: GET /v1/conversations/conv-8f235c63-.../messages, live, 2026-08-19, for an
#: intake whose POST was rejected with 429 and never delivered.
LETTA_CONVERSATION_WITH_NOTHING_DELIVERED = [
    {
        'id': 'message-33598d6a-2373-4205-a7ed-2ca9f71e080b',
        'role': None,
        'message_type': 'system_message',
        'content': 'You are Letta Code, a persistent coding agent...',
    },
]


def test_a_letta_conversation_is_not_born_empty():
    """The false premise, stated as a fact and pinned.

    If a future Letta really does create conversations empty, this fails and
    whoever changes it can decide knowingly -- rather than inheriting a
    comment that was wrong for months.
    """
    assert len(LETTA_CONVERSATION_WITH_NOTHING_DELIVERED) == 1
    assert (LETTA_CONVERSATION_WITH_NOTHING_DELIVERED[0]['message_type']
            == 'system_message')
    assert DispatchEvidence.from_payload(
        LETTA_CONVERSATION_WITH_NOTHING_DELIVERED).dispatch_landed is False


def test_the_old_conversation_shaped_check_would_still_pass_it():
    """Why the probe had to stop reading the conversation object.

    Its `in_context_message_ids` cannot distinguish a system prompt from a
    dispatch, so no amount of care with that field could have been correct.
    """
    conversation = {'in_context_message_ids': ['message-33598d6a']}
    assert bool(conversation.get('in_context_message_ids')) is True   # old: "delivered"
    assert DispatchEvidence.from_payload(conversation).dispatch_landed is False


# ── the round trip nobody checks until it breaks ───────────────────────────

@pytest.mark.parametrize('mode', [AUTOMATIC, SEMI_AUTOMATIC])
def test_a_mode_survives_being_written_and_read_back_as_json(mode, tmp_path):
    """The switch persists through a file. A change to either side that breaks
    the round trip would silently reset the operator's choice on restart."""
    from intake.mazda_mode import JsonFileMazdaModeStore
    path = tmp_path / 'mode.json'
    JsonFileMazdaModeStore(str(path)).write(mode)
    assert json.loads(path.read_text(encoding='utf-8'))['mode'] == mode
    assert JsonFileMazdaModeStore(str(path)).read() == mode


# ── the sweep stays complete as readers are added ─────────────────────────

def test_every_boundary_constructor_is_swept():
    """This file's value is the case nobody anticipated, which is worth nothing
    if the next boundary reader is simply never added to READERS.

    Fails the moment one exists that the sweep does not cover. Coverage is
    read from the READERS registry itself, NOT from this file's source text --
    a first attempt matched against the whole file and an `import` line counted
    as coverage, so a reader could be imported, never swept, and still pass.
    """
    import ast
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    dashboard = os.path.dirname(here)
    constructors = []
    for package in ('finance', 'intake'):
        directory = os.path.join(dashboard, package)
        for filename in sorted(os.listdir(directory)):
            if not filename.endswith('.py'):
                continue
            tree = ast.parse(
                open(os.path.join(directory, filename), encoding='utf-8').read())
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for member in node.body:
                    if (isinstance(member, ast.FunctionDef)
                            and member.name in ('from_http', 'from_payload',
                                                'from_reader')):
                        constructors.append(node.name)

    assert constructors, 'found no boundary constructors -- the scan is broken'
    swept = {name.split('.')[0] for name, _verdict, _unsafe in READERS}
    unswept = sorted(set(constructors) - swept)
    assert not unswept, (
        f'These read data from outside the process and are not in this '
        f'file\'s sweep: {unswept}. Add each to READERS with the answer that '
        f'would be a lie, or state here why it cannot fail open.')
