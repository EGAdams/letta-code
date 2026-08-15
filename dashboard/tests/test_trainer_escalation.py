from intake.trainer_contracts import IntakeCallback, TrainerLaunchRequest
from intake.trainer_escalation import (
    CallbackTrainerEscalationRecorder,
    ProblemOnlyTrainerEscalationService,
)
from intake.trainer_recovery import recover_pending_trainer_watches
import server


class FakeHandle:
    def __init__(self, callback):
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class FakeScheduler:
    def __init__(self):
        self.handles = []

    def schedule(self, _delay_seconds, callback):
        handle = FakeHandle(callback)
        self.handles.append(handle)
        return handle


class RecordingNotifier:
    def __init__(self, launched=True):
        self.launched = launched
        self.requests = []

    def notify(self, request):
        self.requests.append(request)
        return self.launched


class RecordingEscalations:
    def __init__(self):
        self.notices = []

    def record(self, notice):
        self.notices.append(notice)


def request():
    return TrainerLaunchRequest(
        scan_path='/staged/scan_freezer.jpg',
        scanner_name='Freezer Scanner',
        facade_result={'ok': True, 'doc_kind': 'unknown'},
        conversation_id='conv-freezer',
        dispatched_at=1000.0,
    )


def callback(**overrides):
    values = {
        'conversation_id': 'conv-freezer',
        'dispatched_at': 1000.0,
        'parsed': 1,
        'stored': 1,
        'expense_ids': (42,),
        'duplicate_expense_ids': (),
        'deposits_stored': 0,
        'status': '',
    }
    values.update(overrides)
    return IntakeCallback(**values)


def service():
    notifier = RecordingNotifier()
    scheduler = FakeScheduler()
    recorder = RecordingEscalations()
    return (
        ProblemOnlyTrainerEscalationService(
            notifier=notifier,
            scheduler=scheduler,
            callback_timeout_seconds=600,
            recorder=recorder,
        ),
        notifier,
        scheduler,
        recorder,
    )


def test_healthy_callback_cancels_fallback_without_launching_trainer():
    subject, notifier, scheduler, recorder = service()
    subject.watch(request())

    result = subject.observe(callback())

    assert result.matched is True
    assert result.summoned is False
    assert result.reason == ''
    assert notifier.requests == []
    assert scheduler.handles[0].cancelled is True
    assert recorder.notices == []


def test_zero_parsed_and_zero_stored_summons_trainer_immediately():
    subject, notifier, scheduler, recorder = service()
    subject.watch(request())

    result = subject.observe(callback(
        parsed=0,
        stored=0,
        expense_ids=(),
    ))

    assert result.matched is True
    assert result.summoned is True
    assert result.reason == 'callback reported no parsed or persisted records'
    assert notifier.requests == [request()]
    assert scheduler.handles[0].cancelled is True
    assert recorder.notices[0].summoned is True


def test_duplicate_only_callback_is_a_healthy_terminal_outcome():
    subject, notifier, _scheduler, recorder = service()
    subject.watch(request())

    result = subject.observe(callback(
        stored=0,
        expense_ids=(),
        duplicate_expense_ids=(42,),
    ))

    assert result.summoned is False
    assert notifier.requests == []
    assert recorder.notices == []


def test_missing_callback_summons_trainer_after_deadline():
    subject, notifier, scheduler, recorder = service()
    subject.watch(request())

    scheduler.handles[0].callback()

    assert notifier.requests == [request()]
    assert recorder.notices[0].reason == 'expense-stored callback deadline expired'
    assert recorder.notices[0].summoned is True


def test_deadline_recorder_persists_launch_identity_and_outcome():
    notifier = RecordingNotifier()
    scheduler = FakeScheduler()
    events = []
    subject = ProblemOnlyTrainerEscalationService(
        notifier=notifier,
        scheduler=scheduler,
        callback_timeout_seconds=600,
        recorder=CallbackTrainerEscalationRecorder(events.append),
    )
    subject.watch(request())

    scheduler.handles[0].callback()

    assert events == [{
        'conversation_id': 'conv-freezer',
        'document_path': '/staged/scan_freezer.jpg',
        'dispatched_at': 1000.0,
        'trainer_dispatched': True,
        'trainer_escalation_reason': 'expense-stored callback deadline expired',
        'status': 'processing',
        'status_detail': (
            'Trainer summoned: expense-stored callback deadline expired'
        ),
    }]


def test_repeat_problem_callback_cannot_launch_duplicate_trainers():
    subject, notifier, _scheduler, _recorder = service()
    subject.watch(request())
    problem = callback(parsed=0, stored=0, expense_ids=())

    first = subject.observe(problem)
    second = subject.observe(problem)

    assert first.summoned is True
    assert second.matched is False
    assert len(notifier.requests) == 1


def test_expense_stored_problem_callback_summons_trainer_and_keeps_intake_open(
    monkeypatch,
):
    subject, notifier, _scheduler, _recorder = service()
    monkeypatch.setattr(server, '_trainer_escalation_service', subject)
    server.record_recent_intake(
        '/staged/scan_freezer.jpg',
        'Freezer Scanner',
        conversation_id='conv-freezer',
        dispatched_at=1000.0,
    )
    subject.watch(request())

    server.record_stored_expense({
        'document_path': '/staged/scan_freezer.jpg',
        'conversation_id': 'conv-freezer',
        'dispatched_at': 1000.0,
        'parsed': 0,
        'stored': 0,
        'expense_ids': [],
        'duplicate_expense_ids': [],
    })

    intake = server._read_recent_pointer_file()['intake']
    assert notifier.requests == [request()]
    assert intake['status'] == 'processing'
    assert intake['status_detail'].startswith('Trainer summoned:')


def test_restart_recovery_rebuilds_each_pending_watch_once():
    subject, notifier, scheduler, _recorder = service()
    intake = {
        'image_path': '/staged/scan_freezer.jpg',
        'label': 'Freezer Scanner',
        'conversation_id': 'conv-freezer',
        'dispatched_at': 1000.0,
        'doc_kind': 'receipt',
        'vendor': 'Meijer',
        'status': 'processing',
    }
    pointer = {
        'intake': dict(intake),
        'scanner_intakes': {
            'Freezer Scanner': dict(intake),
            'Window Scanner': {
                **intake,
                'conversation_id': 'conv-window',
                'label': 'Window Scanner',
                'status': 'complete',
            },
        },
    }

    recovered = recover_pending_trainer_watches(pointer, subject)

    assert recovered == 1
    assert len(scheduler.handles) == 1
    assert notifier.requests == []


def test_restart_recovery_skips_intake_with_trainer_already_launched():
    subject, _notifier, scheduler, _recorder = service()
    pointer = {
        'intake': {
            'image_path': '/staged/scan_freezer.jpg',
            'label': 'Freezer Scanner',
            'conversation_id': 'conv-freezer',
            'dispatched_at': 1000.0,
            'status': 'processing',
            'trainer_dispatched': True,
        },
    }

    assert recover_pending_trainer_watches(pointer, subject) == 0
    assert scheduler.handles == []
