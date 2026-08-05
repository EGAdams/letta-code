from recent_intake_view import collapse_equivalent_expense_rows


def test_equivalent_duplicate_expenses_collapse_to_oldest_canonical_row():
    rows = [
        {
            "id": 561,
            "date": "2025-02-20",
            "amount": "33.13",
            "description": "MR BURGER RESTAURANT 1",
            "receipt_url": "canonical.jpg",
        },
        {
            "id": 1519,
            "date": "2025-02-20",
            "amount": "33.13",
            "description": "MR BURGER RESTAURANT",
            "receipt_url": "duplicate.png",
        },
    ]

    collapsed, promoted = collapse_equivalent_expense_rows(rows, {561, 1519})

    assert [row["id"] for row in collapsed] == [561]
    assert promoted == {561}


def test_same_date_and_amount_from_different_merchants_remain_separate():
    rows = [
        {"id": 1, "date": "2025-02-20", "amount": "33.13", "description": "MR BURGER"},
        {"id": 2, "date": "2025-02-20", "amount": "33.13", "description": "OFFICE DEPOT"},
    ]

    collapsed, promoted = collapse_equivalent_expense_rows(rows, {1, 2})

    assert [row["id"] for row in collapsed] == [1, 2]
    assert promoted == {1, 2}
