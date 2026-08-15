import json

from intake import trainer_notifier
from intake.trainer_contracts import TrainerLaunchRequest


def request():
    return TrainerLaunchRequest(
        scan_path='/remote/incoming_scans/window_scan.jpg',
        scanner_name='Window Scanner',
        facade_result={'ok': True, 'doc_kind': 'receipt'},
        conversation_id='conv-window',
        dispatched_at=1752170000.0,
    )


def test_build_trainer_command_carries_typed_scan_context():
    command = trainer_notifier.build_trainer_command(
        '/runner',
        '/run_mazda_trainer.mjs',
        request().scan_path,
        request().scanner_name,
        request().facade_result,
        request().dispatched_at,
        request().conversation_id,
    )

    assert command[:2] == ['/runner', '/run_mazda_trainer.mjs']
    assert json.loads(command[command.index('--facade') + 1]) == {
        'ok': True,
        'doc_kind': 'receipt',
    }
    assert command[command.index('--conversation-id') + 1] == 'conv-window'


def test_missing_script_fails_loud_without_spawning():
    notifier = trainer_notifier.DetachedTrainerNotifier(
        '/runner', '/nonexistent/trainer.mjs')

    assert notifier.notify(request()) is False


def test_notifier_spawns_in_detached_systemd_scope(monkeypatch, tmp_path):
    script = tmp_path / 'run_mazda_trainer.mjs'
    script.write_text('// stub')
    spawned = {}

    def fake_popen(command, **kwargs):
        spawned.update(command=command, kwargs=kwargs)

    monkeypatch.setattr(trainer_notifier.subprocess, 'Popen', fake_popen)
    notifier = trainer_notifier.DetachedTrainerNotifier('/runner', str(script))

    assert notifier.notify(request()) is True
    assert spawned['command'][0] == 'systemd-run'
    assert '--scope' in spawned['command']
    assert str(script) in spawned['command']
    assert spawned['kwargs']['start_new_session'] is True
    assert '.bun/bin' in spawned['kwargs']['env']['PATH']
    assert '.npm-global/bin' in spawned['kwargs']['env']['PATH']


def test_notifier_process_failure_is_reported_without_raising(
    monkeypatch, tmp_path
):
    script = tmp_path / 'run_mazda_trainer.mjs'
    script.write_text('// stub')
    monkeypatch.setattr(
        trainer_notifier.subprocess,
        'Popen',
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError('runner missing')),
    )
    notifier = trainer_notifier.DetachedTrainerNotifier('/runner', str(script))

    assert notifier.notify(request()) is False
