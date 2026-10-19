"""Recovery and application validation at the receptionist's save boundary."""
from finance.expense_record_serialization import records_as_json
from finance.expense_edit_version import record_version
from receptionist_work.contracts import BrowserCommand
from receptionist_work.training_editor import TrainingExpenseEditor
from tests.expense_edit_test_fakes import edit, record, repository, row
from adw_modules.receptionist.store import SqliteWorkStore
from receptionist_work.intent_store import SqliteEditIntents


def test_stale_edit_is_rejected_before_sql_or_receipt_side_effects():
    repo, connection = repository([row()])
    original = repo.read(501)
    try:
        repo.apply_edit(edit(expected_version='outdated'))
    except ValueError as error:
        assert 'changed while it was open' in str(error)
    else:
        raise AssertionError('stale edit was accepted')
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert not any(sql.startswith('UPDATE') for sql, _ in connection.cur.executed)
    repo.apply_edit(edit(expected_version=record_version(original)))
    assert connection.commits == 1
    assert any('FOR UPDATE' in sql for sql, _ in connection.cur.executed)


class RecordStore:
    def __init__(self):
        self.value = record(distance_miles=3.0, notes='Preserve me')

    def read(self, expense_id):
        return self.value


class Command:
    def __init__(self, repo):
        self.calls, self.repo = 0, repo

    def execute(self, data):
        self.calls += 1
        self.repo.value = self.repo.value.model_copy(update={'category_id':425})
        return {'ok':True, 'record':records_as_json([self.repo.value])[0], 'changed_fields':['category_id'], 'warnings':[]}


def setup(tmp_path):
    repo = RecordStore()
    command = Command(repo)
    store = SqliteWorkStore(tmp_path / 'work.sqlite')
    expected = records_as_json([repo.value])[0]
    browser = BrowserCommand(id='category-0001', action='category', expense_id=501,
        category_id=425, category_label='Church / Medical / Walgreens (RM) [425]', expected=expected)
    store.enqueue(browser)
    store.claim(browser.id, 'browser-one')
    service = TrainingExpenseEditor(repo, None, command, SqliteEditIntents(tmp_path / 'work.sqlite'))
    data = {'operation_id':browser.id, 'expense_id':501, 'merchant_name':expected['description'],
            'transaction_date':expected['transaction_date'], 'total_amount':expected['total_amount'],
            'distance_miles':3.0, 'map_link':'', 'category_name':browser.category_label}
    return service, repo, command, data


def test_duplicate_delivery_returns_original_receipt_without_another_save(tmp_path):
    service, _, command, data = setup(tmp_path)
    first = service.edit(data)
    assert first['ok']
    assert service.edit(data) == first
    assert command.calls == 1


def test_lost_receipt_is_reconciled_without_repeating_a_committed_save(tmp_path):
    service, repo, command, data = setup(tmp_path)
    repo.value = repo.value.model_copy(update={'category_id':425})
    result = service.edit(data)
    assert result['ok'] and result['reconciled']
    assert command.calls == 0


def test_changed_record_is_not_overwritten(tmp_path):
    service, repo, command, data = setup(tmp_path)
    repo.value = repo.value.model_copy(update={'description':'Changed by someone else'})
    assert not service.edit(data)['ok']
    assert command.calls == 0


def test_other_fields_and_vendor_learning_cannot_escape_training_command(tmp_path):
    service, _, command, data = setup(tmp_path)
    assert not service.edit({**data, 'distance_miles':None})['ok']
    assert not service.edit({**data, 'learn_vendor':True, 'vendor_key':'danger'})['ok']
    assert command.calls == 0


def test_cancelled_browser_cannot_save_late(tmp_path):
    service, _, command, data = setup(tmp_path)
    with SqliteWorkStore(tmp_path / 'work.sqlite').transaction() as db:
        db.execute("UPDATE browser_commands SET status='cancelled'")
    assert not service.edit(data)['ok']
    assert command.calls == 0
