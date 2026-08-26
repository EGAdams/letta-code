"""The fork between Mazda's LLM turn and a human's inbox.

Pointed at intake/mazda_dispatch.py, never at `server`. server.py keeps three
thin wrappers over this module; monkeypatching one of those would rebind a
name the moved code never reads, so a test written that way isolates nothing
while looking exactly like it does.

The expensive failures guarded here, in order of how much they cost:

1. A document that is neither dispatched nor recorded. The operator's page
   shows it spinning on `processing` forever and the scan is, in practice,
   lost -- which is the one outcome ``block_for_human_only`` exists to prevent.
2. A transport failure blamed on the Trainer. Only `status_source ==
   'transport'` may be cleared by a late STEP 8 callback, so the wrong label
   makes a delivered document permanently failed.
3. A Trainer summoned for a run already known dead, at full token price.

Every one of them used to be reachable through a dict literal that
`merge_recent_intake_status` read with `.get()` and defaults, and the sections
marked "the code that used to run" reproduce those literals inline so the day
IntakeOutcome stops earning its keep is visible.
"""

import json
import urllib.error
import urllib.request

import pytest
from pydantic import ValidationError

from intake.mazda_dispatch import (
    Collaborators,
    HUMAN_ONLY_MODE_STAGE_MESSAGE,
    IntakeOutcome,
    OUTCOME_SOURCES,
    TRANSPORT_FAILURE_DETAIL,
    block_for_human_only,
    dispatch_or_block,
    dispatch_was_accepted,
    notify_mazda_of_scan,
    notify_mazda_of_scan_and_record_failure,
)
from intake.mazda_mode import AUTOMATIC, SEMI_AUTOMATIC


class _Recorder:
    """A Collaborators bundle whose five ports all record what they were given."""

    def __init__(self, mode=AUTOMATIC, merge_result=True, messages=None):
        self.mode = mode
        self.merge_result = merge_result
        self.messages = messages if messages is not None else []
        self.merged, self.observed, self.watched, self.asked = [], [], [], []

    def deps(self):
        return Collaborators(
            current_mode=lambda: self.mode,
            watch_intake=lambda *a: self.watched.append(a),
            merge_status=lambda update: (self.merged.append(update)
                                         or self.merge_result),
            observe_callback=lambda payload: self.observed.append(payload),
            letta_get=lambda path, timeout=6: (self.asked.append(path)
                                               or self.messages),
        )


class _NoopThread:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def start(self):
        pass


# ── the record the fork writes when it declines ────────────────────────────

def _outcome(**overrides):
    base = dict(conversation_id='conv-1', document_path='/staged/window.jpg',
                dispatched_at=1787770091.6458578, status='fail',
                status_source='transport', detail='d')
    base.update(overrides)
    return IntakeOutcome(**base)


def test_the_two_outcomes_dump_exactly_what_the_literals_did():
    """Byte-identical to the dicts that shipped inline, key order included --
    merge_recent_intake_status reads this by key and the browser renders what
    it stores, so a reordered or renamed field is a UI change."""
    human_only = _outcome(status='needs_human_review',
                          status_source='human_only_mode',
                          detail=HUMAN_ONLY_MODE_STAGE_MESSAGE).as_update()
    assert human_only == {
        'conversation_id': 'conv-1',
        'document_path': '/staged/window.jpg',
        'dispatched_at': 1787770091.6458578,
        'status': 'needs_human_review',
        'status_source': 'human_only_mode',
        'detail': HUMAN_ONLY_MODE_STAGE_MESSAGE,
    }
    assert list(human_only) == ['conversation_id', 'document_path',
                               'dispatched_at', 'status', 'status_source',
                               'detail']
    transport = _outcome(detail=TRANSPORT_FAILURE_DETAIL).as_update()
    assert transport == {
        'conversation_id': 'conv-1',
        'document_path': '/staged/window.jpg',
        'dispatched_at': 1787770091.6458578,
        'status': 'fail',
        'status_source': 'transport',
        'detail': TRANSPORT_FAILURE_DETAIL,
    }
    # It is JSON that lands in recent_report.json, not a Python object.
    assert json.loads(json.dumps(transport)) == transport


@pytest.mark.parametrize('missing', ['conversation_id', 'status_source',
                                     'dispatched_at', 'detail',
                                     'document_path', 'status'])
def test_every_field_is_required(missing):
    """None of these has a defensible default. Each one's absence is handled
    somewhere downstream by a fallback that does the wrong thing quietly."""
    fields = _outcome().as_update()
    del fields[missing]
    with pytest.raises(ValidationError):
        IntakeOutcome(**fields)


@pytest.mark.parametrize('bad', [None, '', '   '])
def test_a_blank_conversation_id_is_refused(bad):
    """It is the primary correlation key. Blank does not raise downstream --
    it silently demotes the match to document-path-plus-timestamp, which can
    match nothing at all (see the regression below)."""
    with pytest.raises(ValidationError):
        _outcome(conversation_id=bad)


@pytest.mark.parametrize('bad', [None, 0, 0.0, -1.0, '1787770091', 'now'])
def test_dispatched_at_must_be_a_real_timestamp(bad):
    """`'now'` is not hypothetical: the fork's own tests used to pass that
    string straight through. A non-positive or unparseable value makes
    IntakeCallback.from_mapping return None, which turns observe_callback into
    a no-op, which leaves the Trainer's deadline watch armed on a run already
    known dead."""
    with pytest.raises(ValidationError):
        _outcome(dispatched_at=bad)


@pytest.mark.parametrize('status,wrong_source', [
    ('needs_human_review', 'transport'),
    ('fail', 'human_only_mode'),
    ('needs_human_review', 'trainer'),
    ('fail', 'callback'),
])
def test_the_status_and_its_source_may_not_drift(status, wrong_source):
    with pytest.raises(ValidationError):
        _outcome(status=status, status_source=wrong_source)


def test_the_pairing_table_is_the_only_definition():
    assert OUTCOME_SOURCES == {'needs_human_review': 'human_only_mode',
                               'fail': 'transport'}


@pytest.mark.parametrize('status', ['processing', 'complete', 'pass', 'stalled',
                                    'needs_human_reveiw', ''])
def test_only_this_modules_own_two_outcomes_are_accepted(status):
    """A status outside merge_recent_intake_status' terminal set makes the
    merge return False and the document vanish; a terminal one that isn't ours
    (e.g. 'complete') would mark an undispatched document finished."""
    with pytest.raises(ValidationError):
        _outcome(status=status, status_source='transport')


def test_an_unknown_field_is_refused_rather_than_stored():
    """recent_report.json is read back by the report page and by
    _recover_trainer_escalations. A typo'd key used to be persisted silently
    and read by nobody."""
    with pytest.raises(ValidationError):
        IntakeOutcome(**_outcome().as_update(), report_path='/x')


# ── the code that used to run, and what it accepted ────────────────────────
# Reproduced inline rather than described, so these stay true as the modules
# around them change. Each block is the literal that shipped before
# IntakeOutcome, followed by the downstream default that swallowed it.

def _old_merge_reads_status_source(update):
    """The line from merge_recent_intake_status, verbatim."""
    return str(update.get('status_source') or 'trainer').strip()


def _old_recovery_branch_fires(intake_status_source):
    """The branch in _fold_event_into_intake that clears a provisional
    failure. It is the ONLY way a timed-out-but-delivered dispatch is ever
    corrected to 'complete'."""
    return intake_status_source == 'transport'


def test_a_missing_status_source_used_to_blame_the_trainer_forever():
    old_failure_literal = {
        'conversation_id': 'conv-1',
        'document_path': '/staged/window.jpg',
        'dispatched_at': 1787770091.6458578,
        'status': 'fail',
        # 'status_source': 'transport'  <- one deleted line
        'detail': TRANSPORT_FAILURE_DETAIL,
    }
    blamed = _old_merge_reads_status_source(old_failure_literal)
    assert blamed == 'trainer'
    assert _old_recovery_branch_fires(blamed) is False, (
        'a delivered document would stay failed forever')

    with pytest.raises(ValidationError):
        IntakeOutcome(**old_failure_literal)
    assert _old_recovery_branch_fires(
        _old_merge_reads_status_source(
            _outcome(detail=TRANSPORT_FAILURE_DETAIL).as_update())) is True


def test_a_human_only_block_mislabelled_transport_would_be_cleared_by_a_stray_callback():
    """The same accident in the other direction: 'transport' is an invitation
    to any later callback to mark the document complete, removing it from the
    manual queue nobody has processed it from."""
    assert _old_recovery_branch_fires('transport') is True
    assert _old_recovery_branch_fires('human_only_mode') is False
    with pytest.raises(ValidationError):
        _outcome(status='needs_human_review', status_source='transport')


# ── block_for_human_only ───────────────────────────────────────────────────

def test_the_block_records_the_document_as_needing_a_human():
    rec = _Recorder()
    assert block_for_human_only(
        rec.deps(), '/staged/window.jpg', 'conv-1', 1787770091.6) is True
    assert rec.merged == [{
        'conversation_id': 'conv-1',
        'document_path': '/staged/window.jpg',
        'dispatched_at': 1787770091.6,
        'status': 'needs_human_review',
        'status_source': 'human_only_mode',
        'detail': HUMAN_ONLY_MODE_STAGE_MESSAGE,
    }]


def test_the_block_never_arms_a_trainer_watch():
    """Mazda never starts, so no callback can ever arrive; a deadline watch
    would fire ProblemOnlyTrainerEscalationService and spend exactly the
    tokens this mode exists to save."""
    rec = _Recorder()
    block_for_human_only(rec.deps(), '/staged/window.jpg', 'conv-1', 1.0)
    assert rec.watched == [] and rec.observed == []


def test_a_block_that_matched_nothing_is_reported_rather_than_discarded(capsys):
    """The regression this module was extracted around. The old inline version
    threw merge's answer away, so a document that reached no intake record was
    left on the non-terminal 'processing' status -- /recent_report.html
    auto-refreshes on it for the rest of the day and it is never processed."""
    rec = _Recorder(merge_result=False)
    assert block_for_human_only(
        rec.deps(), '/staged/window.jpg', 'conv-1', 1.0) is False
    assert 'will not appear on /recent_report.html' in capsys.readouterr().out


def test_the_message_the_operator_reads_names_the_mode_and_where_to_go():
    assert 'human_only' in HUMAN_ONLY_MODE_STAGE_MESSAGE
    assert '/recent_report.html' in HUMAN_ONLY_MODE_STAGE_MESSAGE


# ── dispatch_or_block: the fork itself ─────────────────────────────────────

def test_semi_automatic_blocks_and_automatic_dispatches(monkeypatch):
    """Moved from tests/test_mazda_mode.py, re-pointed at the owning module."""
    import intake.mazda_dispatch as mod
    threads = []
    monkeypatch.setattr(mod.threading, 'Thread',
                        lambda **kwargs: threads.append(kwargs) or _NoopThread())

    rec = _Recorder(mode=SEMI_AUTOMATIC)
    assert dispatch_or_block(rec.deps(), '/tmp/x.png', 'label', {}, 'conv-1',
                             1787770091.6, lambda: None, ()) is False
    assert len(rec.merged) == 1 and not threads and not rec.watched

    rec.mode = AUTOMATIC
    assert dispatch_or_block(rec.deps(), '/tmp/x.png', 'label', {}, 'conv-1',
                             1787770091.6, lambda: None, ()) is True
    assert len(rec.merged) == 1 and len(threads) == 1 and len(rec.watched) == 1


def test_the_mode_is_asked_per_call_not_captured():
    """The switch takes effect on the NEXT document, not the next restart.
    A bundle built once and held would freeze it."""
    modes = iter([AUTOMATIC, SEMI_AUTOMATIC, AUTOMATIC])
    rec = _Recorder()
    deps = Collaborators(
        current_mode=lambda: next(modes),
        watch_intake=lambda *a: rec.watched.append(a),
        merge_status=lambda u: rec.merged.append(u) or True,
        observe_callback=lambda p: rec.observed.append(p),
        letta_get=lambda path, timeout=6: [])
    seen = [dispatch_or_block(deps, '/tmp/x.png', 'l', {}, 'conv-1',
                              1787770091.6, lambda: None, ())
            for _ in range(3)]
    assert seen == [True, False, True]


def test_the_thread_is_started_with_the_target_it_was_handed(monkeypatch):
    import intake.mazda_dispatch as mod
    captured = {}

    def _thread(**kwargs):
        captured.update(kwargs)
        return _NoopThread()

    monkeypatch.setattr(mod.threading, 'Thread', _thread)
    target, args = object(), ('a', 'b')
    dispatch_or_block(_Recorder().deps(), '/tmp/x.png', 'l', {}, 'conv-1',
                      1787770091.6, target, args)
    assert captured['target'] is target
    assert captured['args'] == args
    assert captured['daemon'] is True


def test_the_watch_is_armed_only_on_the_dispatching_path():
    rec = _Recorder(mode=AUTOMATIC)
    dispatch_or_block(rec.deps(), '/staged/w.jpg', 'Window Scanner', {'ok': True},
                      'conv-1', 1787770091.6, lambda: None, ())
    assert rec.watched == [('/staged/w.jpg', 'Window Scanner', {'ok': True},
                            'conv-1', 1787770091.6)]


# ── dispatch_was_accepted (moved from tests/test_dispatch_evidence.py) ─────

#: What Letta returns for a conversation nothing was ever posted to: the system
#: prompt it is born with. Reproduced from the live stalled intake
#: (conv-8f235c63, 2026-08-19) -- the old probe read this as "delivered".
NOTHING_WAS_DELIVERED = [{'role': None, 'message_type': 'system_message'}]
DISPATCH_DELIVERED = NOTHING_WAS_DELIVERED + [
    {'role': 'user', 'message_type': 'user_message'}]


def test_probe_reports_not_accepted_for_the_live_stalled_conversation():
    rec = _Recorder(messages=NOTHING_WAS_DELIVERED)
    assert dispatch_was_accepted(rec.deps(), 'conv-8f235c63') is False


def test_probe_reports_accepted_once_the_message_is_there():
    rec = _Recorder(messages=DISPATCH_DELIVERED)
    assert dispatch_was_accepted(rec.deps(), 'conv-8f235c63') is True


def test_probe_asks_for_the_messages_not_the_conversation():
    """Reading the conversation object is what made the old check wrong: its
    in_context_message_ids cannot tell a system prompt from a dispatch."""
    rec = _Recorder(messages=[])
    dispatch_was_accepted(rec.deps(), 'conv-8f235c63')
    assert rec.asked and rec.asked[0].endswith('/messages?limit=5')


def test_probe_refuses_a_blank_conversation_id():
    rec = _Recorder(messages=DISPATCH_DELIVERED)
    assert dispatch_was_accepted(rec.deps(), '') is False
    assert rec.asked == []


def test_probe_url_quotes_the_conversation_id():
    rec = _Recorder(messages=[])
    dispatch_was_accepted(rec.deps(), 'conv/../../v1/agents')
    assert '/..' not in rec.asked[0]


# ── notify_mazda_of_scan (moved from tests/test_server.py) ─────────────────

_FACADE_JPEG_UNKNOWN = {'ok': True, 'doc_kind': 'unknown', 'confidence': 0}


class _Resp:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_scan_message_round_trips_through_notify(monkeypatch):
    """notify_mazda_of_scan must POST exactly the built message to Mazda."""
    import intake.mazda_dispatch as mod
    captured = {}

    def _fake_urlopen(req, timeout=0):
        captured['url'] = req.full_url
        captured['body'] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(mod.urllib.request, 'urlopen', _fake_urlopen)
    notify_mazda_of_scan(_Recorder().deps(), '/scans/x.jpg', 'Freezer Scanner',
                         _FACADE_JPEG_UNKNOWN, 'conv-freezer')

    expected = mod.build_scan_message(
        '/scans/x.jpg', 'Freezer Scanner', _FACADE_JPEG_UNKNOWN,
        conversation_id='conv-freezer')
    assert captured['body']['messages'][0]['content'] == expected
    assert captured['url'].endswith('/v1/conversations/conv-freezer/messages')
    assert captured['body']['streaming'] is False


def test_notify_refuses_a_shared_default_conversation():
    """A falsy conversation id would post into Mazda's agent-default
    conversation, where simultaneous Window and Freezer scans share compacted
    context -- the thing isolated conversations exist to stop."""
    rec = _Recorder()
    assert notify_mazda_of_scan(rec.deps(), '/scans/x.jpg', 'Freezer Scanner',
                                _FACADE_JPEG_UNKNOWN, None) is False
    assert rec.asked == []


def _raises(exc):
    def _fake(*args, **kwargs):
        raise exc
    return _fake


def test_scan_notify_timeout_is_success_when_conversation_received_message(monkeypatch):
    """A slow synchronous agent run must not be reported as delivery failure."""
    import intake.mazda_dispatch as mod
    monkeypatch.setattr(mod.urllib.request, 'urlopen',
                        _raises(TimeoutError('timed out')))
    rec = _Recorder(messages=DISPATCH_DELIVERED)
    assert notify_mazda_of_scan(rec.deps(), '/scans/x.jpg', 'Freezer Scanner',
                                _FACADE_JPEG_UNKNOWN, 'conv-freezer') is True


def test_scan_notify_failure_remains_failure_when_conversation_is_empty(monkeypatch):
    import intake.mazda_dispatch as mod
    monkeypatch.setattr(mod.urllib.request, 'urlopen',
                        _raises(TimeoutError('timed out')))
    rec = _Recorder(messages=[])
    assert notify_mazda_of_scan(rec.deps(), '/scans/x.jpg', 'Freezer Scanner',
                                _FACADE_JPEG_UNKNOWN, 'conv-freezer') is False


def test_a_rejected_dispatch_is_reported_as_a_failure(monkeypatch):
    """The 2026-08-19 defect, at the level the operator feels it.

    The POST was rejected with HTTP 429 -- nothing was queued -- and the probe
    saw the system prompt every conversation is born with and called it
    delivered. The scan was recorded `processing` and hung until the Trainer
    reported it as an infrastructure problem.
    """
    import intake.mazda_dispatch as mod
    monkeypatch.setattr(mod.urllib.request, 'urlopen', _raises(
        urllib.error.HTTPError('u', 429, 'Too Many Requests', {}, None)))
    rec = _Recorder(messages=NOTHING_WAS_DELIVERED)
    assert notify_mazda_of_scan(rec.deps(), '/scans/x.jpg', 'Window Scanner',
                                _FACADE_JPEG_UNKNOWN, 'conv-8f235c63') is False


# ── notify_mazda_of_scan_and_record_failure ────────────────────────────────

def test_a_transport_failure_is_recorded_as_provisional(monkeypatch):
    import intake.mazda_dispatch as mod
    monkeypatch.setattr(mod, 'notify_mazda_of_scan', lambda *a, **k: False)
    rec = _Recorder()
    assert notify_mazda_of_scan_and_record_failure(
        rec.deps(), '/staged/window.jpg', 'Window Scanner', {}, 'conv-window',
        1787770091.6) is False
    assert len(rec.merged) == 1
    assert rec.merged[0]['status'] == 'fail'
    assert rec.merged[0]['status_source'] == 'transport'
    assert 'Mazda could not be reached' in rec.merged[0]['detail']


def test_the_failure_reaches_the_trainer_watch_and_the_report_as_one_record(monkeypatch):
    """observe_callback cancels the deadline watch; merge_status is what the
    operator sees. They are handed the same object on purpose -- two
    separately-built dicts is how the two halves disagree about which run
    failed."""
    import intake.mazda_dispatch as mod
    monkeypatch.setattr(mod, 'notify_mazda_of_scan', lambda *a, **k: False)
    rec = _Recorder()
    notify_mazda_of_scan_and_record_failure(
        rec.deps(), '/staged/window.jpg', 'Window Scanner', {}, 'conv-window',
        1787770091.6)
    assert rec.observed == rec.merged
    assert rec.observed[0] is rec.merged[0]


def test_a_delivered_scan_records_nothing(monkeypatch):
    import intake.mazda_dispatch as mod
    monkeypatch.setattr(mod, 'notify_mazda_of_scan', lambda *a, **k: True)
    rec = _Recorder()
    assert notify_mazda_of_scan_and_record_failure(
        rec.deps(), '/staged/window.jpg', 'Window Scanner', {}, 'conv-window',
        1787770091.6) is True
    assert rec.merged == [] and rec.observed == []


# ── production wiring ──────────────────────────────────────────────────────

def test_server_wires_the_real_collaborators():
    """Rule 4: prove production hands over the real objects, not that the
    bundle merely has five fields."""
    import server
    deps = server._mazda_dispatch_deps()
    assert deps.current_mode is server.current_execution_mode
    assert deps.watch_intake is server._watch_intake_for_problems
    assert deps.merge_status is server.merge_recent_intake_status
    assert deps.observe_callback is server._observe_intake_callback
    assert deps.letta_get is server.letta_get


def test_the_bundle_is_rebuilt_per_call_not_captured(monkeypatch):
    """The late binding that makes every monkeypatch of a server-side
    collaborator work, and makes a live switch flip visible to the next scan."""
    import server
    sentinel = object()
    monkeypatch.setattr(server, '_watch_intake_for_problems', sentinel)
    assert server._mazda_dispatch_deps().watch_intake is sentinel


@pytest.mark.parametrize('gone', [
    # the cluster itself
    '_block_dispatch_for_human_only_mode',
    '_mazda_dispatch_was_accepted',
    '_notify_mazda_of_scan',
    'ExecutionModeConfig',
    # re-exports that expired with it: DispatchEvidence had exactly one caller
    # in server.py (_mazda_dispatch_was_accepted) and InvalidExecutionMode is
    # caught by nobody -- an unparseable MAZDA_DECISION_MODE is meant to stop
    # the process, not be handled.
    'DispatchEvidence',
    'InvalidExecutionMode',
])
def test_names_that_moved_are_gone_from_server(gone):
    """Rule 6: a dead re-export cannot creep back, and a test written against
    one would keep passing against an attribute the moved code never reads."""
    import server
    assert not hasattr(server, gone)


@pytest.mark.parametrize('kept,owner', [
    ('resolve_execution_mode', 'intake.mazda_mode'),
    ('HUMAN_ONLY_MODE_STAGE_MESSAGE', 'intake.mazda_dispatch'),
])
def test_the_kept_names_are_the_owning_modules_objects(kept, owner):
    """Both are still called from server.py -- one builds EXECUTION_MODE at
    import, one is the stage_error both intake entry points return."""
    import importlib

    import server
    assert getattr(server, kept) is getattr(importlib.import_module(owner), kept)
