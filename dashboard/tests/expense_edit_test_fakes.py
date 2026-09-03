"""Shared fakes for focused expense-edit tests."""
from finance.category_naming import ICategoryNamer
from finance.expense_edit_model import ExpenseEdit, ExpenseRecord
from finance.expense_edit_repository import MySqlExpenseRecordRepository
from finance.expense_schema import ExpenseSchema, IExpenseSchemaProbe


class FakeNamer(ICategoryNamer):
    NAMES = {140: 'Office', 243: 'Rosemary'}

    def name_for(self, category_id):
        return self.NAMES.get(category_id, '')

    def id_for(self, category_name):
        name = (category_name or '').strip()
        if not name:
            return None
        for category_id, label in self.NAMES.items():
            if label == name:
                return category_id
        raise ValueError(f'Unknown category: {name!r}')


class FakeProbe(IExpenseSchemaProbe):
    def __init__(self, available=('id_light',)):
        self._available = frozenset(available)

    def read(self, cur, candidates):
        return ExpenseSchema(available=self._available)


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)
        self.executed = []
        self._result = []

    def execute(self, sql, params=()):
        self.executed.append((' '.join(sql.split()), tuple(params)))
        if sql.lstrip().upper().startswith('UPDATE'):
            self._result = []
            return
        self._result = list(self._rows)

    def fetchall(self):
        return list(self._result)

    def fetchone(self):
        return self._result[0] if self._result else None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection:
    def __init__(self, rows):
        self.cur = FakeCursor(rows)
        self.commits = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def row(**overrides):
    value = {
        'id': 501,
        'expense_date': '2026-08-15',
        'amount': 12.34,
        'description': 'Kroger',
        'category_id': 140,
        'id_light': 'kroger_08_15_26_12_34',
        'source_file': '',
    }
    value.update(overrides)
    return value


def repository(rows, probe=None, relocator=None):
    connection = FakeConnection(rows)
    repo = MySqlExpenseRecordRepository(
        lambda: connection,
        FakeNamer(),
        schema_probe=probe or FakeProbe(),
        relocator=relocator,
    )
    return repo, connection


def edit(**overrides):
    fields = dict(
        expense_id=501,
        merchant_name='Kroger Fuel',
        transaction_date='2026-08-15',
        total_amount=12.34,
        category_id=140,
    )
    fields.update(overrides)
    return ExpenseEdit(**fields)


def record(**overrides):
    fields = dict(
        id=501,
        transaction_date='2026-08-15',
        total_amount=12.34,
        description='Kroger',
        id_light='kroger_08_15_26_12_34',
        category_id=140,
        category_name='Office',
    )
    fields.update(overrides)
    return ExpenseRecord(**fields)
