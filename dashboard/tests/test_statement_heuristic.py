"""Tests for the zero-cost "does this look like a statement?" heuristic.

Runs over the exact raw OCR text local OCR produced for the real 2026-08-19
Last Window Scan (Choice Privileges Mastercard) -- captured verbatim from a
live --engine local run, not invented -- alongside synthetic receipt text that
must NOT trigger it.
"""
from finance.statement_heuristic import (
    MULTI_TRANSACTION_LINE_THRESHOLD,
    count_dated_amount_lines,
    looks_like_multiple_transactions,
)

# Captured verbatim (meta.raw_text) from a real --engine local run against
# window_scan_1787148790798854142_445cdee49064.jpg.
REAL_STATEMENT_RAW_TEXT = (
    "Choice Privileges® Mastercard® Account Number Ending i -. "
    "24-Hour Customer Service: 1-833-714-3490\n"
    "Billing Cycle 05/23/2025 to 0/207, We accept all relay calls, including.711\n"
    "Wells Fargo Online®: wellsfargo.com\n\n"
    "Payment Information — :\n\n"
    "New Balance\nMinimum Payment Due $ 25.00\nPayment Due Date 07/16/2025\n\n"
    "I Transaction ‘Summary _\n\n"
    "Trans Date Post Date Reference Number \"Description of Transaction or "
    "Credit BO Amount\n"
    "05/22 06/23 680001000 55436874F4ZMOTSWW QUALITY INNS JASPER TN $93.99\n\n"
    "FOLIO#081 2670215 ARRIVE 05/22/25 DEPART 05/23/25\n"
    "06/22 05/23 000001700 55310204F65FA24VA ECONO LODGE VALDOSTA GA $87.80\n"
    "FOLIO#0812400250 ARRIVE 05/21/25 DEPART 05/22/25 ,\n"
    "05/23 05/23 740001500 02305374GEJ134D7L CRACKER BARREL #428 CA CAVE CITY KY\n"
    "06/31 05/31 000000083 85741 104TIRTY85DZ PAYMENT - THANK YOU\n"
    "ELLIS SEARS LOT GRAND RAPIDS MI\n\n"
    "_06/ 07 780001400 55546504ZAM041KE2\n\n"
    "06/20 2=Ssié«i2tt~«*S Be _— Interest Charge on Purchases —\n"
    "TOTAL INTEREST FOR THIS PERIOD\n\n"
    "PURCHASE(S) N/A N/A 24.24% (v) $0.00 $0.00 $140.45\n"
    "Continued on next page\n"
)

# Captured verbatim (tesseract, --engine local) from the real 2026-08-19 Last
# Freezer Scan -- the DTE gas bill that scored ZERO dated lines and got no
# nudge, which is what sent EG looking for the missing dialog. Every date on
# the page is spelled out; the Summary of Charges column prints bare decimals.
DTE_BILL_RAW_TEXT = (
    "MULTIPLE BILL STATEMENTS ENCLOSED F octiciees IF'op News coat\n"
    "42667 1 AV 0.495\"\u2014T155*2*P00*M08**AUTO**SCH 5-DIGIT 4950 "
    "Due September 05, 2025 $28.08\n\n"
    "RIVER OF LIFE Total Due: $28.07\n\n"
    "GRAND RAPIDS MI 49504-2674 Mail Payments to: S\n"
    "\u2014\u2014 Summary of Snarges [Atcount Number 9100 210 8054 4]\n"
    "Account Balance as of Jul 14, 2025 24.16\n"
    "Payment Received Jul 26, 2025 Thank You! \u2014 24.15\n\n"
    "Balance Prior to Current Charges 0.01\n\n"
    "Total Current Charges 28.06\n"
    "Account Balance as of August 14, 2025 $28.07\n\n"
    "Your current charges are due on September 05, 2025. A 2% late payment "
    "charge will be applied if paid after the due date.\n"
)

SINGLE_ITEM_RECEIPT_RAW_TEXT = (
    "MR BURGER RESTAURANT\n"
    "02/20/2025 6:41 PM\n\n"
    "1  Burger Combo         $9.99\n"
    "1  Fries                $2.50\n"
    "1  Soda                 $1.99\n\n"
    "Subtotal              $14.48\n"
    "Tax                    $0.87\n"
    "Total                  $15.35\n"
    "Approved USD $15.35\n"
)

GROCERY_RECEIPT_RAW_TEXT = (
    "KROGER\n06/15/2025\n\n"
    "MILK 2%              $3.49\n"
    "BREAD WHEAT           $2.99\n"
    "EGGS DOZEN            $4.29\n"
    "BANANAS                $1.12\n"
    "CHICKEN BREAST        $8.76\n\n"
    "SUBTOTAL              $20.65\n"
    "TAX                    $1.24\n"
    "TOTAL                 $21.89\n"
)


def test_real_statement_page_crosses_the_threshold():
    assert count_dated_amount_lines(REAL_STATEMENT_RAW_TEXT) >= 2
    assert looks_like_multiple_transactions(REAL_STATEMENT_RAW_TEXT) is True


def test_single_item_receipt_does_not_trigger():
    assert looks_like_multiple_transactions(SINGLE_ITEM_RECEIPT_RAW_TEXT) is False


def test_itemized_grocery_receipt_does_not_trigger():
    # Multiple dollar amounts, but no per-line date -- exactly what a
    # date+amount-per-line requirement is meant to tell apart from a
    # statement's transaction table.
    assert looks_like_multiple_transactions(GROCERY_RECEIPT_RAW_TEXT) is False


def test_empty_or_missing_text_never_triggers():
    assert looks_like_multiple_transactions('') is False
    assert looks_like_multiple_transactions(None) is False
    assert count_dated_amount_lines(None) == 0


def test_exactly_one_dated_amount_line_is_not_enough():
    one_line = "05/23 QUALITY INNS JASPER TN $93.99\nno date or amount here\n"
    assert count_dated_amount_lines(one_line) == 1
    assert looks_like_multiple_transactions(one_line) is False


def test_threshold_is_the_documented_constant():
    two_lines = "05/23 A $1.00\n05/24 B $2.00\n"
    assert count_dated_amount_lines(two_lines) == MULTI_TRANSACTION_LINE_THRESHOLD
    assert looks_like_multiple_transactions(two_lines) is True


def test_iso_dates_are_recognized_too():
    text = "2025-05-23 A $1.00\n2025-05-24 B $2.00\n"
    assert looks_like_multiple_transactions(text) is True


def test_amount_without_dollar_sign_does_not_count():
    # A bare number could be a reference number, a quantity, or a percentage
    # -- requiring the '$' keeps this from over-triggering on those.
    text = "05/23 A 93.99\n05/24 B 87.80\n"
    assert looks_like_multiple_transactions(text) is False


def test_dte_bill_with_month_name_dates_triggers():
    # The regression this whole month-name branch exists for: a real utility
    # bill whose every date is spelled out. Before it, this page scored 0 and
    # the operator saw no "Break up Document" nudge at all -- so one $28.07
    # expense got entered by hand for a page headed MULTIPLE BILL STATEMENTS
    # ENCLOSED.
    assert count_dated_amount_lines(DTE_BILL_RAW_TEXT) >= 2
    assert looks_like_multiple_transactions(DTE_BILL_RAW_TEXT) is True


def test_month_name_dates_are_recognized_in_both_forms():
    abbreviated = "Jul 14, 2025 A $1.00\nAug 14, 2025 B $2.00\n"
    spelled_out = "September 05, 2025 A $1.00\nOctober 5 2025 B $2.00\n"
    assert looks_like_multiple_transactions(abbreviated) is True
    assert looks_like_multiple_transactions(spelled_out) is True


def test_month_name_alone_without_a_day_is_not_a_date():
    # A bare month name is a heading ("August Charges"), not a transaction
    # date -- requiring a day number after it keeps those from counting.
    text = "August Charges $1.00\nSeptember Charges $2.00\n"
    assert looks_like_multiple_transactions(text) is False
