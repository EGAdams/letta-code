import server


def test_window_scan_collapses_equivalent_duplicate_ids(monkeypatch):
    monkeypatch.setattr(server, '_fetch_expenses_by_ids', lambda ids: [
        {
            'id': 561, 'date': '2025-02-20', 'amount': '33.13',
            'vendor_key': 'mr_burger', 'description': 'MR BURGER RESTAURANT 1',
            'reporting_category': 'Food & Hospitality',
            'cat_class': 'cat-food-and-hospitality', 'receipt_url': 'canonical.jpg',
        },
        {
            'id': 1519, 'date': '2025-02-20', 'amount': '33.13',
            'vendor_key': 'mr_burger_restaurant', 'description': 'MR BURGER RESTAURANT',
            'reporting_category': 'Food & Hospitality',
            'cat_class': 'cat-food-and-hospitality', 'receipt_url': 'duplicate.png',
        },
    ])
    monkeypatch.setattr(server, '_receipt_only_picker_assets',
                        lambda: ('', '<div id="rol-category-picker"></div>', ''))
    intake = {
        'document': 'window_scan.jpg', 'label': 'Window Scanner',
        'expense_ids': [561, 1519], 'duplicate_expense_ids': [561, 1519],
        'parsed': 1, 'stored': 0, 'status': 'complete',
    }

    html = server.build_recent_intake_html(intake)

    assert html.count('data-expense-id="561"') == 1
    assert 'data-expense-id="1519"' not in html
