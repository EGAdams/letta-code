"""Michigan sales tax as a rule, not a number copied around.

The "Add 6%" button on a Verified Transactions row asks for exactly one thing:
this expense was recorded at the pre-tax figure printed on the page, put the
sales tax back on it. Two facts decide the answer -- the state's rate, and how
money rounds -- and both belong in one place:

* the browser must not own the rate. A tax rate that lives in a script tag is a
  rate that drifts from the one the reports were built with, and nobody notices
  until a quarter is off by a few dollars;
* the arithmetic must not be a float multiply. ``28.73 * 1.06`` is
  30.454399999999996 in binary floating point, and which way that lands after
  rounding is an accident of the representation. Decimal with an explicit
  ROUND_HALF_UP is the same rule a cash register applies.

Nothing here touches a database, an HTTP request, or a report -- the caller
decides which row to apply it to.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

#: Michigan's statewide sales tax. There are no local add-ons to fold in: the
#: state does not permit municipal sales taxes, so one rate covers every row
#: this dashboard files.
MICHIGAN_SALES_TAX_RATE = Decimal('0.06')

#: Money is stored to the cent; every result is quantized to it.
CENTS = Decimal('0.01')


def as_rate(value=None) -> Decimal:
    """Coerce a rate to Decimal, defaulting to Michigan's.

    Accepts the float an HTTP body carries (via ``str()``, never
    ``Decimal(float)``, which would import the float's binary error into the
    exact arithmetic this module exists to provide). A rate outside 0..1 is a
    caller mistake -- 6 instead of 0.06 -- and is refused rather than silently
    charging 600% tax.
    """
    if value is None or value == '':
        return MICHIGAN_SALES_TAX_RATE
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'not a tax rate: {value!r}') from None
    if rate < 0 or rate > 1:
        raise ValueError('tax rate must be between 0 and 1 (0.06 for 6%)')
    return rate


def tax_on(amount, rate=None) -> Decimal:
    """The tax alone, rounded to the cent."""
    try:
        base = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'not an amount: {amount!r}') from None
    return (base * as_rate(rate)).quantize(CENTS, rounding=ROUND_HALF_UP)


def with_sales_tax(amount, rate=None) -> Decimal:
    """`amount` plus its sales tax, rounded to the cent.

    The tax is rounded first and then added, which is what a receipt does: the
    line the operator is reconciling against shows a whole-cent tax, so
    rounding the total instead would disagree with the paper by a cent on some
    rows and not others.
    """
    try:
        base = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'not an amount: {amount!r}') from None
    return (base.quantize(CENTS, rounding=ROUND_HALF_UP)
            + tax_on(base, rate))
