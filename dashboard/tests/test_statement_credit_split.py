"""Tests for the pure payment/credit/zero-amount classifier.

This mirrors store_statement_transactions.py's split_expenses_and_credits
exactly (same three rules, over the same set of rows) so the operator's
Prev/Next review list agrees with what the store was always going to do with
each row. The store re-derives its own answer independently at save time --
this module's only job is to keep the obviously-not-an-expense rows off the
list the operator edits.
"""
from finance.statement_credit_split import reviewable_flags


def test_zero_amount_is_never_reviewable():
    assert reviewable_flags([(0.0, 'Interest Charge on Purchases')]) == [False]


def test_mixed_sign_page_flags_the_positive_amount_as_a_credit():
    """The Last Window Scan's actual page: four purchases, one payment."""
    rows = [
        (-93.99, 'QUALITY INNS JASPER TN'),
        (-87.80, 'ECONO LODGE VALDOSTA GA'),
        (-28.73, 'CRACKER BARREL #428 CAVE CITY KY'),
        (2900.00, 'PAYMENT - THANK YOU'),
        (-6.00, 'ELLIS SEARS LOT GRAND RAPIDS MI'),
        (0.00, 'Interest Charge on Purchases'),
    ]
    assert reviewable_flags(rows) == [True, True, True, False, True, False]


def test_all_positive_page_falls_back_to_the_description_pattern():
    """Sign alone carries no information once every amount is the same sign
    -- a positive amount here must not be flagged a credit just for being
    positive; only the description pattern decides."""
    rows = [(12.34, 'GROCERY STORE'), (45.00, 'GAS STATION')]
    assert reviewable_flags(rows) == [True, True]


def test_all_positive_page_still_catches_a_payment_by_description():
    rows = [(12.34, 'GROCERY STORE'), (2900.00, 'PAYMENT - THANK YOU')]
    assert reviewable_flags(rows) == [True, False]


def test_all_negative_page_falls_back_to_the_description_pattern_too():
    rows = [(-12.34, 'GROCERY STORE'), (-45.00, 'AUTOPAY WEBSITE')]
    assert reviewable_flags(rows) == [True, False]


def test_pattern_matches_are_case_insensitive_and_word_bounded():
    """'DEPOSIT ONLY BANKING CENTER' should match; 'CREDIT VALLEY DINER'
    should match on the word 'credit', not on a substring like 'accredited'."""
    rows = [
        (5.0, 'accredited college bookstore'),
        (5.0, 'CREDIT VALLEY DINER'),
        (5.0, 'quarterly refund processing'),
    ]
    assert reviewable_flags(rows) == [True, False, False]


def test_empty_page_returns_no_flags():
    assert reviewable_flags([]) == []
