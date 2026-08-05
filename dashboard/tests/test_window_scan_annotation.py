from document_annotation import ExpenseEvidence, _best_line


def test_ocr_damaged_total_outranks_exact_approval_confirmation():
    target = ExpenseEvidence(
        561,
        "2025-02-20",
        "33.13",
        "MR BURGER RESTAURANT",
        "mr_burger_restaurant",
    )
    lines = [
        ("TOTAL 33.1", (1019, 634, 1566, 658)),
        ("Uta receipt noise TOTAL 33.1", (1019, 560, 1589, 591)),
        ("Approved USD $33.13", (1009, 1324, 1572, 1354)),
    ]

    region, score, text = _best_line(lines, target)

    assert score >= 7
    assert text == "TOTAL 33.1"
    assert region == (1019, 634, 1566, 658)
