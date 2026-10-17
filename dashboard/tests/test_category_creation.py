"""Category/vendor creation is independent of expense writes; all storage is fake."""
from unittest.mock import MagicMock, Mock

import pytest

from finance.category_creation import create_category_vendor


REQUEST = {'parent_id': 140, 'name': 'Printer ink', 'vendor_key': 'ink_store',
           'description': 'Ink Store'}
CATEGORY = {'id': 999, 'name': 'Church / Office / Printer ink [999]'}


def setup(known=None):
    creator = Mock()
    creator.get_or_create.return_value = 999
    lookup = Mock()
    lookup.vendor_map = known or {}
    lookup.add_vendor_key.return_value = True
    catalog = Mock()
    catalog.options.return_value = [CATEGORY]
    catalog.name_for.side_effect = lambda cid: 'Church / Office [140]' if cid == 140 else CATEGORY['name']
    deps = dict(creator=creator, lookup_factory=lambda: lookup, catalog=catalog, invalidate=Mock())
    return deps, creator, lookup


def test_creates_category_and_remembers_exact_vendor_without_expense_writes():
    deps, creator, lookup = setup()
    assert create_category_vendor(REQUEST, **deps) == dict(ok=True, category=CATEGORY, vendor_key='ink_store')
    creator.get_or_create.assert_called_once_with(140, 'Printer ink')
    lookup.add_vendor_key.assert_called_once_with('ink_store', 999, raw_description='Ink Store')
    deps['invalidate'].assert_called_once()


def test_repeat_is_idempotent_but_cannot_repoint_vendor_to_another_parent():
    deps, creator, lookup = setup({'ink_store': 999})
    assert create_category_vendor(REQUEST, **deps)['ok']
    result = create_category_vendor(dict(REQUEST, parent_id=1), **deps)
    assert not result['ok']
    assert 'already belongs' in result['error']
    creator.get_or_create.assert_not_called()
    lookup.add_vendor_key.assert_not_called()


def test_vendor_failure_explains_saved_category_and_allows_retry():
    deps, creator, lookup = setup()
    lookup.add_vendor_key.side_effect = OSError('Read-only vendor store')
    result = create_category_vendor(REQUEST, **deps)
    assert not result['ok']
    assert 'category was saved' in result['error']
    assert 'vendor key was not saved' in result['error']
    assert 'Read-only' in result['error']


def test_existing_vendor_shows_current_category_before_any_write():
    deps, creator, lookup = setup({'ink_store': 140})
    result = create_category_vendor(REQUEST, **deps)
    assert result['code'] == 'vendor_category_conflict'
    assert result['conflict']['current_category'] == {'id': 140, 'name': 'Church / Office [140]'}
    assert result['conflict']['proposed_category_name'] == 'Church / Office / Printer ink'
    creator.get_or_create.assert_not_called()
    lookup.reassign_vendor_key.assert_not_called()


def test_explicit_confirmation_moves_existing_vendor_to_new_child():
    deps, creator, lookup = setup({'ink_store': 140})
    result = create_category_vendor(dict(REQUEST, expected_vendor_category_id=140), **deps)
    assert result == dict(ok=True, category=CATEGORY, vendor_key='ink_store')
    creator.get_or_create.assert_called_once_with(140, 'Printer ink')
    lookup.reassign_vendor_key.assert_called_once_with('ink_store', 999, expected_category_id=140)
    lookup.add_vendor_key.assert_not_called()


def test_stale_confirmation_returns_fresh_conflict_without_creating_category():
    deps, creator, lookup = setup({'ink_store': 3})
    result = create_category_vendor(dict(REQUEST, expected_vendor_category_id=140), **deps)
    assert result['conflict']['current_category']['id'] == 3
    creator.get_or_create.assert_not_called()
    lookup.reassign_vendor_key.assert_not_called()


def test_confirmation_for_removed_vendor_does_not_recreate_it():
    deps, creator, lookup = setup()
    result = create_category_vendor(dict(REQUEST, expected_vendor_category_id=140), **deps)
    assert not result['ok']
    creator.get_or_create.assert_not_called()
    lookup.add_vendor_key.assert_not_called()


@pytest.mark.parametrize('bad', [None, [], dict(REQUEST, parent_id='140'),
    dict(REQUEST, vendor_key='Not a key!'), dict(REQUEST, description='bad\nYAML'),
    dict(REQUEST, expense_id=501), dict(REQUEST, name='')])
def test_invalid_input_has_no_storage_side_effects(bad):
    deps, creator, lookup = setup()
    assert not create_category_vendor(bad, **deps)['ok']
    creator.get_or_create.assert_not_called()
    lookup.add_vendor_key.assert_not_called()


def test_category_creator_reuses_existing_child_and_rejects_missing_parent():
    from finance.category_creation_repository import MySqlCategoryCreator
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {'id': 140}
    cursor.fetchall.return_value = [{'id': 999, 'is_active': 1, 'retired_at': None, 'kind': 'EXPENSE'}]
    creator = MySqlCategoryCreator(lambda: connection)
    assert creator.get_or_create(140, 'Printer ink') == 999
    assert not any('INSERT' in call.args[0] for call in cursor.execute.call_args_list)
    connection.commit.assert_called_once()
    cursor.fetchone.return_value = None
    with pytest.raises(ValueError, match='active expense parent'):
        creator.get_or_create(777, 'Printer ink')
    connection.rollback.assert_called_once()


def test_new_child_inherits_accounting_axes_without_modifying_expenses():
    from finance.category_creation_repository import MySqlCategoryCreator
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {'id': 140}
    cursor.fetchall.return_value = []
    cursor.lastrowid = 999
    assert MySqlCategoryCreator(lambda: connection).get_or_create(140, 'Printer ink') == 999
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    insert = next(sql for sql in statements if sql.startswith('INSERT'))
    assert 'excluded_from_nonprofit_totals' in insert
    assert 'functional_class' in insert
    assert 'per_expense_only' in insert
    assert all('expenses' not in sql for sql in statements)


def test_real_vendor_store_round_trip_uses_only_temporary_yaml(monkeypatch, tmp_path):
    from finance import vendor_lookup
    monkeypatch.syspath_prepend(vendor_lookup.CATEGORIZER_LIB_DIR)
    from vendor_category_lookup import VendorCategoryLookup
    lookup = VendorCategoryLookup.__new__(VendorCategoryLookup)
    lookup.vendor_yaml_path = tmp_path / 'vendor_category.yaml'
    lookup.vendor_yaml_path.write_text('')
    lookup.vendor_map, lookup.alias_patterns, lookup.category_names = {}, {}, {}
    deps, _, _ = setup()
    deps['lookup_factory'] = lambda: lookup
    assert create_category_vendor(REQUEST, **deps)['ok']
    lookup.vendor_map, lookup.alias_patterns = {}, {}
    lookup._load_vendor_categories()
    assert lookup.vendor_map == {'ink_store': 999}
    before = lookup.vendor_yaml_path.read_text()
    assert create_category_vendor(REQUEST, **deps)['ok']
    assert lookup.vendor_yaml_path.read_text() == before


def test_confirmed_move_round_trip_uses_canonical_store_and_retries_safely(monkeypatch, tmp_path):
    from finance import vendor_lookup
    monkeypatch.syspath_prepend(vendor_lookup.CATEGORIZER_LIB_DIR)
    from vendor_category_lookup import VendorCategoryLookup
    lookup = VendorCategoryLookup.__new__(VendorCategoryLookup)
    lookup.vendor_yaml_path = tmp_path / 'vendor_category.yaml'
    lookup.vendor_yaml_path.write_text('')
    lookup.vendor_map, lookup.alias_patterns, lookup.category_names = {}, {}, {}
    lookup.add_vendor_key('ink_store', 140, raw_description='Ink Store')
    deps, creator, _ = setup()
    deps['lookup_factory'] = lambda: lookup
    original = lookup.vendor_yaml_path.read_text()
    assert create_category_vendor(REQUEST, **deps)['code'] == 'vendor_category_conflict'
    assert lookup.vendor_yaml_path.read_text() == original
    confirmed = dict(REQUEST, expected_vendor_category_id=140)
    assert create_category_vendor(confirmed, **deps)['ok']
    lookup.vendor_map, lookup.alias_patterns = {}, {}
    lookup._load_vendor_categories()
    assert lookup.find_vendor_match('Ink Store').category_id == 999
    saved = lookup.vendor_yaml_path.read_text()
    assert create_category_vendor(confirmed, **deps)['ok']
    assert lookup.vendor_yaml_path.read_text() == saved
    creator.get_or_create.assert_called_once()
