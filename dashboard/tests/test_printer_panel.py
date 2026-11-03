"""The Printer tab's backend: it only runs adw_printer.py, never prints without confirm and the switch."""
from monitoring import printer_panel as pp

LINE = pp.MARKER + '{"printers": [{"printer_id": "hp_8120e", "name": "HP"}], "default": "hp_8120e", ' \
                   '"documents": [{"name": "private.pdf"}], "recent": []}'


def test_result_line_is_the_last_marker_line():
    assert pp.result_line('noise\n' + LINE + '\n')['default'] == 'hp_8120e'
    assert pp.result_line('no marker here') is None
    assert pp.result_line(pp.MARKER + 'not json') is None


def test_payload_counts_documents_without_naming_them():
    payload = pp.build_payload(pp.result_line(LINE), True, 1.0).model_dump()
    assert payload['ok'] and payload['documents'] == 1 and payload['default'] == 'hp_8120e'
    assert 'private.pdf' not in str(payload)


def test_an_adw_error_is_shown_not_raised():
    payload = pp.build_payload({'error': 'boom'}, False, 1.0)
    assert not payload.ok and payload.error == 'boom' and payload.printers == []


def test_test_print_needs_confirm(monkeypatch, tmp_path):
    flag = tmp_path / 'enabled'
    flag.touch()
    monkeypatch.setattr(pp, 'ENABLED_FLAG', flag)
    launched = []
    for body in ({}, {'confirm': 'yes'}, {'confirm': 1}):
        assert not pp.start_test_print(body, launch=launched.append)['ok']
    assert launched == []


def test_test_print_needs_the_switch(monkeypatch, tmp_path):
    monkeypatch.setattr(pp, 'ENABLED_FLAG', tmp_path / 'missing')
    launched = []
    answer = pp.start_test_print({'confirm': True}, launch=launched.append)
    assert not answer['ok'] and 'switched off' in answer['message'] and launched == []


def test_confirmed_test_print_launches_once_with_a_valid_id(monkeypatch, tmp_path):
    flag = tmp_path / 'enabled'
    flag.touch()
    monkeypatch.setattr(pp, 'ENABLED_FLAG', flag)
    launched = []
    answer = pp.start_test_print({'confirm': True, 'text': 'ignored'}, launch=launched.append)
    assert answer['ok'] and launched == [answer['job_id']]
    assert pp.JOB_ID.fullmatch(answer['job_id']) and 'not proof' in answer['message']


def test_cancel_rejects_bad_ids_without_running_anything(monkeypatch):
    ran = []
    monkeypatch.setattr(pp, '_run', lambda *a, **k: ran.append(a) or {})
    for body in ({}, {'job_id': '../x'}, {'job_id': 'a b c d e f'}, {'job_id': 7}):
        assert not pp.cancel_job(body)['ok']
    assert ran == []


def test_cancel_passes_the_id_to_the_adw(monkeypatch):
    ran = []
    monkeypatch.setattr(pp, '_run', lambda args, **k: ran.append(args) or {'job': {'state': 'canceled'}})
    answer = pp.cancel_job({'job_id': 'd_0123456789ab'})
    assert answer['ok'] and ran == [['cancel', '--job-id', 'd_0123456789ab']]


def test_payload_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(pp, '_run', lambda args, **k: calls.append(args) or pp.result_line(LINE))
    monkeypatch.setattr(pp, '_cache', {'at': 0.0, 'payload': None})
    pp.printer_payload()
    pp.printer_payload()
    assert calls == [['discover']]
    pp.printer_payload(refresh=True)
    assert len(calls) == 2
