import json
from intake_event_store import IIntakeEventStore, JsonIntakeEventStore


def test_missing_and_corrupt_json_read_as_empty_object(tmp_path):
    store = JsonIntakeEventStore(tmp_path / 'recent_intake.json')

    assert store.read() == {}
    assert store.snapshot().startswith('intake:')

    path = tmp_path / 'recent_intake.json'
    path.write_text('{not-json', encoding='utf-8')
    assert store.read() == {}

    path.write_text('[1, 2, 3]', encoding='utf-8')
    assert store.read() == {}


def test_write_is_atomic_and_snapshot_changes_with_persisted_state(tmp_path):
    store = JsonIntakeEventStore(tmp_path / 'recent_intake.json')

    first = store.write({'pointer': {'kind': 'scan', 'name': 'freezer'}})
    assert first.startswith('intake:')
    assert store.read()['pointer'] == {'kind': 'scan', 'name': 'freezer'}

    raw = json.loads((tmp_path / 'recent_intake.json').read_text(encoding='utf-8'))
    assert raw['pointer']['kind'] == 'scan'
    assert not (tmp_path / 'recent_intake.json.tmp').exists()

    second = store.write({'pointer': {'kind': 'pdf', 'name': 'invoice'}})
    assert second != first
    assert store.snapshot() == second
    assert store.read()['pointer'] == {'kind': 'pdf', 'name': 'invoice'}


def test_change_token_changes_when_persisted_metadata_changes(tmp_path):
    path = tmp_path / 'recent_intake.json'
    path.write_text(
        json.dumps({'pointer': {'document': 'scan-1.jpg'}, '_updated_at': 1}),
        encoding='utf-8',
    )
    store = JsonIntakeEventStore(path)

    token1 = store.snapshot()
    path.write_text(
        json.dumps({'pointer': {'document': 'scan-1.jpg'}, '_updated_at': 99}),
        encoding='utf-8',
    )
    token2 = store.snapshot()

    assert token1 != token2


def test_snapshot_is_deterministic_for_the_same_persisted_pointer(tmp_path):
    store = JsonIntakeEventStore(tmp_path / 'recent_intake.json')

    token1 = store.write({'pointer': {'document': 'scan-1.jpg'}})
    token2 = store.snapshot()
    assert token2 == token1

    token3 = store.snapshot()
    assert token3 == token1


def test_non_object_json_reads_as_empty_object(tmp_path):
    path = tmp_path / 'recent_intake.json'
    path.write_text('[]', encoding='utf-8')

    store = JsonIntakeEventStore(path)
    assert store.read() == {}
    assert store.snapshot().startswith('intake:')


def test_protocol_shape_accepts_the_json_store(tmp_path):
    assert isinstance(JsonIntakeEventStore(tmp_path / 'x.json'), IIntakeEventStore)
