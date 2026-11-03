"""The /api/scan-bridge/v1 façade: token, scope, loopback, and what each route returns."""

import hashlib
import json
import os

import pytest

from scan_jobs import composition
from scan_jobs.auth import SCOPES, AuthError, TokenAuthorizer
from scan_jobs.http_routes import PREFIX, BridgeRequest, scan_bridge_dispatch
from scan_jobs.scala_filings import LedgerScalaFilings
from tests.scan_jobs_fakes import Rig, jpeg

TOKEN = 'test-token-not-a-secret-0123456789'


def _clients(path, scopes=SCOPES, mode=0o600):
    path.write_text(json.dumps({'clients': [{'name': 'agent-bridge-worker', 'scopes': list(scopes),
                                             'token_sha256': hashlib.sha256(TOKEN.encode()).hexdigest()}]}))
    os.chmod(path, mode)
    return TokenAuthorizer(path)


@pytest.fixture
def rig(tmp_path, monkeypatch):
    built = Rig(tmp_path)
    auth = _clients(tmp_path / 'clients.json')
    monkeypatch.setattr(composition, '_built', (built.service, auth, built.repo))
    built.ledger = tmp_path / 'scala' / 'ledger.jsonl'
    monkeypatch.setattr(composition, '_filings', LedgerScalaFilings(built.ledger, clock_ns=built.clock))
    return built


def call(method, path, body=b'', token=TOKEN, ip='127.0.0.1', **headers):
    path, _, query = path.partition('?')
    hdrs = {k.replace('_', '-'): v for k, v in headers.items()}
    if token:
        hdrs['authorization'] = f'Bearer {token}'
    response = scan_bridge_dispatch(BridgeRequest(method=method, path=PREFIX + path, query=query,
                                                  headers=hdrs, client_ip=ip, body=body))
    data = json.loads(response.body) if response.content_type == 'application/json' else response.body
    return response.code, data, dict(response.headers)


# -- auth ------------------------------------------------------------------------------
@pytest.mark.parametrize('ip, ok', [('127.0.0.1', True), ('::1', True), ('::ffff:127.0.0.1', True),
                                    ('10.0.0.5', False), ('100.102.209.100', False), ('nonsense', False)])
def test_only_loopback_callers_get_in(tmp_path, ip, ok):
    auth = _clients(tmp_path / 'c.json')
    headers = {'authorization': f'Bearer {TOKEN}'}
    if ok:
        assert auth.authorize(ip, headers, 'scanner:status') == 'agent-bridge-worker'
    else:
        with pytest.raises(AuthError) as err:
            auth.authorize(ip, headers, 'scanner:status')
        assert err.value.http == 403


@pytest.mark.parametrize('headers, http', [
    ({}, 401),
    ({'authorization': 'Bearer wrong-token'}, 401),
    ({'authorization': f'Basic {TOKEN}'}, 401),
    ({'authorization': f'Bearer {TOKEN}', 'origin': 'http://evil.example'}, 403),
    ({'authorization': f'Bearer {TOKEN}', 'sec-fetch-site': 'cross-site'}, 403),
])
def test_tokens_are_required_and_browsers_are_refused(tmp_path, headers, http):
    with pytest.raises(AuthError) as err:
        _clients(tmp_path / 'c.json').authorize('127.0.0.1', headers, 'scanner:status')
    assert err.value.http == http


def test_a_token_is_limited_to_its_scopes(tmp_path):
    auth = _clients(tmp_path / 'c.json', scopes=('scanner:status',))
    with pytest.raises(AuthError) as err:
        auth.authorize('127.0.0.1', {'authorization': f'Bearer {TOKEN}'}, 'scanner:start')
    assert (err.value.code, err.value.http) == ('insufficient_scope', 403)


def test_a_readable_client_file_fails_closed(tmp_path):
    auth = _clients(tmp_path / 'c.json', mode=0o644)
    with pytest.raises(AuthError) as err:
        auth.authorize('127.0.0.1', {'authorization': f'Bearer {TOKEN}'}, 'scanner:status')
    assert err.value.http == 503
    with pytest.raises(AuthError) as err:
        TokenAuthorizer(tmp_path / 'missing.json').authorize('127.0.0.1', {}, 'scanner:status')
    assert err.value.http == 401


# -- routes ----------------------------------------------------------------------------
def test_start_then_read_the_document_it_made(rig):
    rig.scanner.next_bytes['window'] = jpeg((200, 10, 10), size=(850, 1100))
    code, started, _ = call('POST', '/scans', json.dumps({'scanner': 'window', 'idempotency_key': 'req-00000001'}).encode())
    assert code == 202 and started['replayed'] is False
    scan_id = started['scan_id']
    code, again, _ = call('POST', '/scans', json.dumps({'scanner': 'window', 'idempotency_key': 'req-00000001'}).encode())
    assert (code, again['scan_id'], again['replayed']) == (200, scan_id, True)

    code, status, _ = call('GET', f'/scans/{scan_id}')
    assert (code, status['status'], status['mazda']) == (200, 'captured', {'status': 'pending'})
    code, doc, _ = call('GET', f'/scans/{scan_id}/document')
    assert doc['page_count'] == 1 and doc['mime_type'] == 'image/jpeg'
    code, image, headers = call('GET', f'/scans/{scan_id}/pages/1?rendition=preview')
    assert code == 200 and image.startswith(b'\xff\xd8') and headers['X-Scan-Id'] == scan_id
    code, original, headers = call('GET', f'/scans/{scan_id}/original')
    assert original == rig.scanner.next_bytes['window'] and headers['X-Artifact-Sha256'] == doc['sha256']
    code, text, _ = call('GET', f'/scans/{scan_id}/text?page=1')
    assert code == 200 and text['text'] == 'OCR TEXT' and 'untrusted' in text['notice']
    code, listing, _ = call('GET', '/scans?limit=5')
    assert [s['scan_id'] for s in listing['scans']] == [scan_id]


def test_the_start_body_takes_only_a_scanner_and_a_key(rig):
    for body in (b'not json', b'[]', json.dumps({'scanner': 'window', 'script': '/bin/sh'}).encode(),
                 json.dumps({'scanner': 'window', 'idempotency_key': 'a b;c'}).encode()):
        code, data, _ = call('POST', '/scans', body)
        assert code == 400, body
    code, data, _ = call('POST', '/scans', json.dumps({'scanner': '/dev/sg0'}).encode())
    assert (code, data['error']['code']) == (400, 'invalid_scanner')
    assert rig.scanner.calls == []


@pytest.mark.parametrize('path, code', [
    ('/scans/../../etc/passwd', 404), ('/scans/scan_bad', 400), ('/scans/scan_01ARZ3NDEKTSV4RRFFQ69G5FAV', 404),
    ('/scans/scan_01ARZ3NDEKTSV4RRFFQ69G5FAV/secrets', 404), ('/files', 404),
])
def test_scans_are_found_only_by_a_well_formed_server_id(rig, path, code):
    assert call('GET', path)[0] == code


def test_a_failed_scan_has_no_document(rig):
    rig.scanner.next_result['freezer'] = {'status': 'offline', 'error': 'not found'}
    _, started, _ = call('POST', '/scans', json.dumps({'scanner': 'freezer'}).encode())
    code, err, _ = call('GET', f"/scans/{started['scan_id']}/pages/1")
    assert (code, err['error']['code']) == (409, 'document_unavailable')
    _, status, _ = call('GET', f"/scans/{started['scan_id']}")
    assert (status['status'], status['error_code']) == ('failed', 'device_offline')


def test_refusals_carry_codes_and_retry_after(rig):
    call('POST', '/scans', json.dumps({'scanner': 'window'}).encode())
    code, err, headers = call('POST', '/scans', json.dumps({'scanner': 'window'}).encode())
    assert (code, err['error']['code']) == (429, 'rate_limited') and int(headers['Retry-After']) > 0
    rig.settings = rig.settings.model_copy(update={'bridge_start_enabled': False})
    code, err, _ = call('POST', '/scans', json.dumps({'scanner': 'freezer'}).encode())
    assert (code, err['error']['code']) == (403, 'bridge_scans_disabled')


def test_no_token_no_answer(rig):
    assert call('GET', '/scans', token=None)[0] == 401
    assert call('POST', '/scans', b'{"scanner":"window"}', token=None)[0] == 401
    assert call('GET', '/scans', ip='192.168.1.20')[0] == 403
    assert rig.scanner.calls == []


# -- Mazda -----------------------------------------------------------------------------
def test_mazda_is_matched_by_hash_and_snapshotted(rig):
    rig.scanner.next_bytes['window'] = jpeg((11, 22, 33))
    _, started, _ = call('POST', '/scans', b'{"scanner":"window"}')
    scan_id = started['scan_id']
    sha = rig.service.get(scan_id).artifact.sha256
    rig.intakes['window'] = {'content_sha256': 'f' * 64, 'status': 'pass', 'vendor': 'Someone Else'}
    assert call('GET', f'/scans/{scan_id}/mazda')[1]['mazda']['status'] == 'pending'

    rig.intakes['window'] = {'content_sha256': sha, 'status': 'processing'}
    assert call('GET', f'/scans/{scan_id}/mazda')[1]['mazda']['status'] == 'running'
    rig.intakes['window'] = {'content_sha256': sha, 'status': 'needs_human_review', 'doc_kind': 'receipt',
                             'vendor': 'Meijer', 'status_detail': 'total unreadable'}
    mazda = call('GET', f'/scans/{scan_id}/mazda')[1]['mazda']
    assert (mazda['status'], mazda['outcome'], mazda['vendor']) == ('completed', 'needs_human_review', 'Meijer')

    rig.intakes['window'] = {'content_sha256': 'e' * 64, 'status': 'fail'}    # the next scan moved on
    assert call('GET', f'/scans/{scan_id}/mazda')[1]['mazda']['vendor'] == 'Meijer'


def test_no_intake_turns_unavailable_after_the_window(rig):
    _, started, _ = call('POST', '/scans', b'{"scanner":"window"}')
    rig.clock.advance(901)
    mazda = call('GET', f"/scans/{started['scan_id']}/mazda")[1]['mazda']
    assert mazda['status'] == 'unavailable' and mazda['warnings']


def test_a_failed_non_finance_document_is_out_of_mazdas_scope(rig):
    _, started, _ = call('POST', '/scans', b'{"scanner":"window"}')
    sha = rig.service.get(started['scan_id']).artifact.sha256
    rig.intakes['window'] = {'content_sha256': sha, 'status': 'fail', 'doc_kind': 'tax_document',
                             'vendor': 'City Income Tax', 'status_detail': 'vendor_key_resolved failed'}
    mazda = call('GET', f"/scans/{started['scan_id']}/mazda")[1]['mazda']
    assert (mazda['status'], mazda['outcome'], mazda['doc_kind']) == ('completed', 'out_of_scope', 'tax_document')
    assert 'Scala' in mazda['detail'] and 'fail' in mazda['warnings'][0]


def test_a_scan_left_for_scala_is_out_of_mazdas_scope_not_a_failure(rig):
    from intake.scala_handoff import LEFT_FOR_SCALA
    _, started, _ = call('POST', '/scans', b'{"scanner":"window"}')
    sha = rig.service.get(started['scan_id']).artifact.sha256
    rig.intakes['window'] = {'content_sha256': sha, 'status': 'complete', 'doc_kind': 'unknown',
                             'status_detail': LEFT_FOR_SCALA.format(kind='tax_document')}
    mazda = call('GET', f"/scans/{started['scan_id']}/mazda")[1]['mazda']
    assert (mazda['status'], mazda['outcome']) == ('completed', 'out_of_scope')
    assert mazda['detail'].startswith('Left for Scala:')


def test_a_failed_receipt_is_still_a_failure(rig):
    _, started, _ = call('POST', '/scans', b'{"scanner":"window"}')
    sha = rig.service.get(started['scan_id']).artifact.sha256
    rig.intakes['window'] = {'content_sha256': sha, 'status': 'fail', 'doc_kind': 'receipt'}
    mazda = call('GET', f"/scans/{started['scan_id']}/mazda")[1]['mazda']
    assert (mazda['status'], mazda['outcome']) == ('failed', 'fail')


# -- Scala -----------------------------------------------------------------------------
def _ledger(rig, *entries):
    rig.ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(rig.ledger, 'a') as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + '\n')


def test_scalas_filing_is_found_by_hash_without_its_path(rig):
    _, started, _ = call('POST', '/scans', b'{"scanner":"window"}')
    scan_id = started['scan_id']
    assert call('GET', f'/scans/{scan_id}/mazda')[1]['scala']['status'] == 'pending'
    sha = rig.service.get(scan_id).artifact.sha256
    _ledger(rig, {'sha256': 'f' * 64, 'decision': 'filed', 'folder': 'someone_else'},
            {'at': '2026-11-01T22:47:09-05:00', 'sha256': sha, 'decision': 'filed', 'folder': 'bills_511/consumers',
             'destination': '/mnt/c/Users/x/secret.jpg', 'method': 'rules', 'confidence': 0.97, 'reason': 'a bill'})
    scala = call('GET', f'/scans/{scan_id}/mazda')[1]['scala']
    assert (scala['status'], scala['folder'], scala['method'], scala['confidence']) == \
        ('filed', 'bills_511/consumers', 'rules', 0.97)
    assert 'destination' not in scala and 'secret' not in json.dumps(scala)


@pytest.mark.parametrize('decision, status, folder', [('inbox', 'inbox', None), ('mazda', 'handed_to_mazda', None),
                                                      ('error', 'error', None), ('surprise', 'error', None)])
def test_scalas_other_decisions(rig, decision, status, folder):
    _, started, _ = call('POST', '/scans', b'{"scanner":"window"}')
    sha = rig.service.get(started['scan_id']).artifact.sha256
    _ledger(rig, {'sha256': sha, 'decision': decision, 'folder': 'unsure', 'confidence': 'n/a'})
    scala = call('GET', f"/scans/{started['scan_id']}/mazda")[1]['scala']
    assert (scala['status'], scala['folder'], scala['confidence']) == (status, folder, None)


def test_a_duplicate_names_where_the_first_copy_went(rig):
    _, started, _ = call('POST', '/scans', b'{"scanner":"window"}')
    sha = rig.service.get(started['scan_id']).artifact.sha256
    _ledger(rig, {'sha256': sha, 'decision': 'filed', 'folder': 'documents_511/taxes'},
            'not json', {'sha256': sha, 'decision': 'duplicate', 'folder': None})
    scala = call('GET', f"/scans/{started['scan_id']}/mazda")[1]['scala']
    assert (scala['status'], scala['folder']) == ('duplicate', 'documents_511/taxes')


def test_no_ledger_line_turns_unavailable_after_the_window(rig):
    _, started, _ = call('POST', '/scans', b'{"scanner":"window"}')
    rig.clock.advance(901)
    scala = call('GET', f"/scans/{started['scan_id']}/mazda")[1]['scala']
    assert scala['status'] == 'unavailable' and scala['warnings']
