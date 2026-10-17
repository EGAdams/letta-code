"""Full editor vocabulary and exact-category saves (no live database writes)."""
import pytest

from category_taxonomy import CategoryNode, StaticCategoryTaxonomy
from finance.category_naming import TaxonomyCategoryNamer
from finance.expense_categories import ExpenseCategoryCatalog
from finance.expense_edit_model import ExpenseRecord
from finance.expense_record_serialization import records_as_json


def catalog():
    taxonomy = StaticCategoryTaxonomy([
        CategoryNode(id=1, parent_id=None, name='Church'),
        CategoryNode(id=120, parent_id=1, name='Utilities'),
        CategoryNode(id=123, parent_id=120, name='Electric Bill'),
        CategoryNode(id=300, parent_id=None, name='Housing'),
        CategoryNode(id=314, parent_id=300, name='Electric Bill'),
        CategoryNode(id=900, parent_id=300, name='Retired', is_active=False),
        CategoryNode(id=3, parent_id=None, name='Personal'),
    ])
    fallback = TaxonomyCategoryNamer(lambda cid: 'Church Utilities',
        lambda name: (120, 'cat-utilities') if name == 'Church Utilities' else (None, None))
    return ExpenseCategoryCatalog(lambda: taxonomy, fallback)


def test_all_active_categories_are_offered_even_without_report_selectable_flag():
    options = catalog().options()
    assert {row['id'] for row in options} == {1, 120, 123, 300, 314, 3}
    assert catalog().name_for(123) == 'Church / Utilities / Electric Bill [123]'
    assert catalog().name_for(314) == 'Housing / Electric Bill [314]'
    for row in options:
        assert catalog().id_for(row['name']) == row['id']


def test_unknown_or_inactive_exact_choices_are_rejected():
    for name in ['Housing / Retired [900]', 'Wrong name [123]', 'Invented [999]']:
        with pytest.raises(ValueError):
            catalog().id_for(name)
    assert catalog().id_for('Church Utilities') == 120
    assert catalog().id_for('') is None


def test_search_serialization_includes_exact_id_in_addition_to_reporting_name():
    row = ExpenseRecord(id=5, transaction_date='2025-01-01', total_amount=5.0,
                        category_id=123, category_name='Church Utilities')
    assert records_as_json([row])[0]['category_id'] == 123


def test_http_port_uses_same_catalog_for_choices_and_audited_save(monkeypatch):
    import server
    from http_app.registry import current_ports
    monkeypatch.setattr(server, '_get_category_taxonomy', catalog()._taxonomy)
    monkeypatch.setattr(server, 'taxonomy_category_namer', lambda: catalog()._fallback)
    captured = []
    def edit(data, namer):
        captured.append(namer.id_for(data['category_name']))
        return {'ok': True}
    monkeypatch.setattr(server, 'edit_stored_expense', edit)
    port = current_ports().expense
    for row in port.categories()['categories']:
        assert port.edit_stored_expense({'category_name': row['name']})['ok']
    assert set(captured) == {1, 120, 123, 300, 314, 3}


def test_catalog_endpoint_over_http(monkeypatch):
    import server
    from tests.http_app_harness import DashboardClient, ServiceRecorder, start_server
    ServiceRecorder().install(monkeypatch)
    monkeypatch.setattr(server, '_get_category_taxonomy', catalog()._taxonomy)
    httpd, thread, port = start_server()
    try:
        response = DashboardClient(port).get('/api/expense-categories')
        assert response.status == 200
        assert {row['id'] for row in response.json['categories']} == {1, 120, 123, 300, 314, 3}
    finally:
        httpd.shutdown()
        httpd.server_close()
