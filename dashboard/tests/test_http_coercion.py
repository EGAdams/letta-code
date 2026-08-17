"""Tests for the untrusted-JSON scalar boundary.

The hole these exist for: `bool` is a subclass of `int` in Python, so
`int(True)` is 1 and `float(True)` is 1.0. Four handlers coerced inline and
all four accepted a JSON `true` as a number -- confirmed against the live
endpoint, where {"expense_id": true} got as far as "no expense with id 1".
"""
import pytest

from finance.http_coercion import (
    as_float, as_int, as_optional_float, as_optional_int)


# --- booleans are not numbers ----------------------------------------------

@pytest.mark.parametrize('value', [True, False])
def test_as_int_refuses_a_boolean(value):
    with pytest.raises(ValueError, match='not a boolean'):
        as_int(value, 'expense_id')


@pytest.mark.parametrize('value', [True, False])
def test_as_float_refuses_a_boolean(value):
    with pytest.raises(ValueError, match='not a boolean'):
        as_float(value, 'total_amount')


def test_the_optional_variants_refuse_booleans_too():
    with pytest.raises(ValueError, match='not a boolean'):
        as_optional_int(True, 'limit')
    with pytest.raises(ValueError, match='not a boolean'):
        as_optional_float(True, 'amount')


def test_false_is_refused_rather_than_read_as_zero():
    # False would otherwise become 0, which reads as "no limit" / "$0.00"
    # rather than as the malformed request it is.
    with pytest.raises(ValueError):
        as_int(False, 'org_id')


# --- ordinary coercion still works -----------------------------------------

@pytest.mark.parametrize('value,expected', [
    (5, 5), ('5', 5), (5.0, 5), ('  7 ', 7), (-3, -3), (0, 0),
])
def test_as_int_accepts_the_usual_shapes(value, expected):
    assert as_int(value, 'expense_id') == expected


@pytest.mark.parametrize('value,expected', [
    (12.34, 12.34), ('12.34', 12.34), (12, 12.0), ('  1e2 ', 100.0), (0, 0.0),
])
def test_as_float_accepts_the_usual_shapes(value, expected):
    assert as_float(value, 'total_amount') == pytest.approx(expected)


def test_a_float_string_is_truncated_by_as_int_not_rejected():
    # int('5.9') raises, but int(5.9) truncates -- document which one happens.
    assert as_int(5.9, 'x') == 5
    with pytest.raises(ValueError):
        as_int('5.9', 'x')


# --- rejections name the field ---------------------------------------------

@pytest.mark.parametrize('value', [None, '', 'abc', [], {}, 'twelve'])
def test_as_float_rejects_non_numbers(value):
    with pytest.raises(ValueError, match='total_amount'):
        as_float(value, 'total_amount')


@pytest.mark.parametrize('value', [None, '', 'abc', [], {}])
def test_as_int_rejects_non_numbers(value):
    with pytest.raises(ValueError, match='expense_id'):
        as_int(value, 'expense_id')


def test_the_message_names_the_offending_field_so_the_operator_can_act():
    with pytest.raises(ValueError) as caught:
        as_float('nope', 'total_amount')
    assert str(caught.value) == 'total_amount must be a number'


# --- absent vs malformed ---------------------------------------------------

@pytest.mark.parametrize('value', [None, ''])
def test_optional_helpers_treat_absent_as_not_supplied(value):
    assert as_optional_float(value, 'amount') is None
    assert as_optional_int(value, 'limit') is None


def test_optional_helpers_still_reject_a_malformed_value():
    with pytest.raises(ValueError):
        as_optional_float('abc', 'amount')
    with pytest.raises(ValueError):
        as_optional_int('abc', 'limit')


def test_zero_is_a_supplied_value_not_an_absent_one():
    assert as_optional_float(0, 'amount') == 0.0
    assert as_optional_int(0, 'limit') == 0


# --- NaN / infinity ---------------------------------------------------------

@pytest.mark.parametrize('text', ['nan', 'inf', '-inf', 'Infinity'])
def test_float_accepts_nan_and_infinity_strings(text):
    # float() does accept these; the Pydantic models downstream are what
    # reject them (total_amount must be > 0, and NaN fails that comparison).
    result = as_float(text, 'total_amount')
    assert result != result or result in (float('inf'), float('-inf'))
