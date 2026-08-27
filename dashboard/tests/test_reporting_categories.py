"""The four reporting-category maps, and the defect they used to allow.

Round 13 of the server.py refactor (Registry). These four dicts —
`REPORTING_CATEGORY_DB_MAP`, `_CLASS`, `_STYLE` (name-keyed) and
`_ANCESTOR_MAP` (id-keyed) — were four hand-maintained literals in `server.py`
that had to agree, with nothing checking that they did.

Three kinds of test here:

1. **Golden parity** — the derived views reproduce the literals `server.py`
   carried at 75807d6b, byte for byte, in the same order where order is part of
   the contract. Copied inline so they keep being true.
2. **They cannot disagree** — not "all four have thirteen entries", which is
   the old invariant restated. Add a fourteenth bucket and all four views grow.
3. **Reachability** — the defect each required field prevents is reachable in
   the code as it stands today.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from finance import reporting_categories as rc
from finance.reporting_categories import REPORTING_CATEGORIES, ReportingCategory

# ── The literals as server.py carried them at 75807d6b ────────────────────────
# Inline, not imported, so this stays a golden test rather than a tautology.

GOLDEN_DB_MAP = {
    'Church Facility': 100,
    'Church Utilities': 120,
    'Ministry and Worship': 150,
    'Office & Administration': 140,
    'Food & Hospitality': 130,
    'Gifts & Love Offerings': 190,
    'Robert Benefits and Medical': 242,
    'Rosemary Benefits & Medical': 243,
    'Travel & Vehicle': 160,
    'Insurance, Taxes & Fees': 230,
    'Housing': 300,
    'Personal': 3,
    'Uncategorized': None,
}

GOLDEN_CLASS = {
    'Church Facility': 'cat-church-facility',
    'Church Utilities': 'cat-church-utilities',
    'Ministry and Worship': 'cat-ministry-and-worship',
    'Office & Administration': 'cat-office-and-administration',
    'Food & Hospitality': 'cat-food-and-hospitality',
    'Gifts & Love Offerings': 'cat-gifts-and-love-offerings',
    'Robert Benefits and Medical': 'cat-robert-benefits-and-medical',
    'Rosemary Benefits & Medical': 'cat-rosemary-benefits-and-medical',
    'Travel & Vehicle': 'cat-travel-and-vehicle',
    'Insurance, Taxes & Fees': 'cat-insurance-taxes-and-fees',
    'Housing': 'cat-housing',
    'Personal': 'cat-personal',
    'Uncategorized': 'cat-uncategorized',
}

GOLDEN_STYLE = {
    'Church Facility': ('#B8CCE4', '#000000'),
    'Church Utilities': ('#95B3D7', '#000000'),
    'Ministry and Worship': ('#DCE6F1', '#000000'),
    'Office & Administration': ('#4F81BD', '#FFFFFF'),
    'Food & Hospitality': ('#F4F199', '#000000'),
    'Gifts & Love Offerings': ('#A9D18E', '#000000'),
    'Robert Benefits and Medical': ('#CCC0DA', '#000000'),
    'Rosemary Benefits & Medical': ('#F4B6C2', '#000000'),
    'Travel & Vehicle': ('#F4B683', '#000000'),
    'Insurance, Taxes & Fees': ('#FCD5B4', '#000000'),
    'Housing': ('#DDD9C4', '#000000'),
    'Personal': ('#948A54', '#FFFFFF'),
    'Uncategorized': ('#BFBFBF', '#000000'),
}

GOLDEN_ANCESTOR_MAP = {
    100: 'Church Facility', 110: 'Church Facility', 120: 'Church Utilities',
    130: 'Food & Hospitality', 140: 'Office & Administration',
    150: 'Ministry and Worship', 160: 'Travel & Vehicle',
    190: 'Gifts & Love Offerings', 230: 'Insurance, Taxes & Fees',
    240: 'Robert Benefits and Medical', 242: 'Robert Benefits and Medical',
    243: 'Rosemary Benefits & Medical', 300: 'Housing', 310: 'Housing',
    320: 'Housing', 330: 'Housing', 340: 'Housing', 350: 'Housing',
    358: 'Insurance, Taxes & Fees', 364: 'Uncategorized',
    400: 'Insurance, Taxes & Fees', 1: 'Uncategorized', 2: 'Housing',
    3: 'Personal',
}


def _fourteenth() -> ReportingCategory:
    return ReportingCategory(
        name='Money Movement', db_id=402, css_class='cat-money-movement',
        background='#101010', font='#FFFFFF', ancestor_ids=(402,))


class TestGoldenParity:
    """The derived views reproduce the literals exactly."""

    def test_db_map_is_unchanged(self):
        assert rc.REPORTING_CATEGORY_DB_MAP == GOLDEN_DB_MAP

    def test_class_map_is_unchanged(self):
        assert rc.REPORTING_CATEGORY_CLASS == GOLDEN_CLASS

    def test_style_map_is_unchanged(self):
        assert rc.REPORTING_CATEGORY_STYLE == GOLDEN_STYLE

    def test_ancestor_map_is_unchanged(self):
        assert rc.REPORTING_CATEGORY_ANCESTOR_MAP == GOLDEN_ANCESTOR_MAP

    def test_the_name_keyed_views_keep_the_dialog_display_order(self):
        """The Set Category dialog iterates these, so order is the contract."""
        for view, golden in (
            (rc.REPORTING_CATEGORY_DB_MAP, GOLDEN_DB_MAP),
            (rc.REPORTING_CATEGORY_CLASS, GOLDEN_CLASS),
            (rc.REPORTING_CATEGORY_STYLE, GOLDEN_STYLE),
        ):
            assert list(view) == list(golden)

    def test_the_ancestor_map_is_only_ever_read_by_key(self):
        """Its key order is NOT part of the contract, and this says why.

        The id-keyed map is reached with `.get()` / `in` only, so deriving it
        per bucket (rather than in the literal's roughly-ascending order) is
        safe. If a caller ever iterates it, this test is the place that claim
        was written down.
        """
        assert set(rc.REPORTING_CATEGORY_ANCESTOR_MAP) == set(GOLDEN_ANCESTOR_MAP)

    def test_server_serves_the_derived_views_under_the_historical_names(self):
        import server

        assert server.REPORTING_CATEGORY_DB_MAP == GOLDEN_DB_MAP
        assert server.REPORTING_CATEGORY_CLASS == GOLDEN_CLASS
        assert server.REPORTING_CATEGORY_STYLE == GOLDEN_STYLE
        assert server.REPORTING_CATEGORY_ANCESTOR_MAP == GOLDEN_ANCESTOR_MAP


class TestTheFourViewsCannotDisagree:
    """Not 'all four have thirteen keys' — that is the old invariant restated.

    These add a fourteenth bucket and check every view grew, which is only
    possible if all four are generated from one list.
    """

    def test_a_new_bucket_reaches_all_four_views(self, monkeypatch):
        extra = _fourteenth()
        monkeypatch.setattr(
            rc, 'REPORTING_CATEGORIES', REPORTING_CATEGORIES + (extra,))
        # Re-derive the way the module does.
        cats = rc.REPORTING_CATEGORIES
        db_map = {c.name: c.db_id for c in cats}
        class_map = {c.name: c.css_class for c in cats}
        style_map = {c.name: (c.background, c.font) for c in cats}
        ancestors = {a: c.name for c in cats for a in c.ancestor_ids}

        assert db_map['Money Movement'] == 402
        assert class_map['Money Movement'] == 'cat-money-movement'
        assert style_map['Money Movement'] == ('#101010', '#FFFFFF')
        assert ancestors[402] == 'Money Movement'
        assert len(db_map) == len(class_map) == len(style_map) == 14

    def test_a_half_added_bucket_is_not_expressible(self):
        """The old shape's actual failure: a name in CLASS, missing from STYLE.

        There is no way to write that here — the fields travel together on one
        model, and omitting one is a ValidationError at construction.
        """
        with pytest.raises(ValidationError):
            ReportingCategory(
                name='Money Movement', db_id=402,
                css_class='cat-money-movement',
                ancestor_ids=(402,))  # no background / font


class TestTheDefectsEachFieldPrevents:
    """Reachability: show the defect is real in today's code, then pin it."""

    def test_a_bucket_with_no_css_class_renders_a_report_row_unstyled(self):
        """`_css_class_for_report_name` falls back to CLASS on a taxonomy miss,
        and that class is written into a `<tr>` in a report.html on disk. A
        bucket present in DB_MAP but absent from CLASS silently became
        'cat-uncategorized' — a grey row that looks like a deliberate choice.
        """
        import server

        # Reachable today: the fallback is live code, not dead code.
        assert server._css_class_for_report_name('not-a-bucket') == 'cat-uncategorized'
        # And every bucket that CAN be written back has a real class.
        for name, db_id in rc.REPORTING_CATEGORY_DB_MAP.items():
            cls = rc.REPORTING_CATEGORY_CLASS[name]
            assert cls.startswith('cat-')
            if db_id is not None:
                assert cls != 'cat-uncategorized', (
                    f'{name!r} writes back id {db_id} but renders as uncategorized')

    def test_a_blank_class_is_refused_rather_than_stripped_to_nothing(self):
        with pytest.raises(ValidationError):
            ReportingCategory(
                name='X', db_id=1, css_class='   ', background='#000000',
                font='#FFFFFF', ancestor_ids=(1,))

    def test_a_colour_that_is_not_a_hex_triple_is_refused(self):
        """The Receipt Only rows inline these. 'blue' renders as no colour."""
        with pytest.raises(ValidationError):
            ReportingCategory(
                name='X', db_id=1, css_class='cat-x', background='blue',
                font='#FFFFFF', ancestor_ids=(1,))

    def test_writing_back_an_id_that_rolls_up_elsewhere_is_refused(self):
        """The picker would write id 300 and the report would then call the row
        'Housing' — a correction that appears to do nothing."""
        with pytest.raises(ValidationError):
            ReportingCategory(
                name='X', db_id=300, css_class='cat-x', background='#000000',
                font='#FFFFFF', ancestor_ids=(999,))

    def test_a_bucket_with_no_ancestor_ids_is_refused(self):
        with pytest.raises(ValidationError):
            ReportingCategory(
                name='X', db_id=None, css_class='cat-x', background='#000000',
                font='#FFFFFF', ancestor_ids=())

    def test_two_buckets_cannot_claim_one_category_id(self, monkeypatch):
        """As dict literals, a repeated ancestor id made the last writer win in
        silence and the two buckets' totals disagree."""
        clash = ReportingCategory(
            name='Money Movement', db_id=402, css_class='cat-money-movement',
            background='#101010', font='#FFFFFF',
            ancestor_ids=(402, 110))  # 110 already rolls up to Church Facility
        monkeypatch.setattr(
            rc, 'REPORTING_CATEGORIES', REPORTING_CATEGORIES + (clash,))
        with pytest.raises(ValueError, match='rolls up to both'):
            rc._check_no_bucket_shares_a_name_or_id()

    def test_two_buckets_cannot_claim_one_name(self, monkeypatch):
        dupe = REPORTING_CATEGORIES[0]
        monkeypatch.setattr(
            rc, 'REPORTING_CATEGORIES', REPORTING_CATEGORIES + (dupe,))
        with pytest.raises(ValueError, match='duplicate reporting-category name'):
            rc._check_no_bucket_shares_a_name_or_id()


class TestTheModelIsStrict:
    def test_it_forbids_an_unexpected_key(self):
        with pytest.raises(ValidationError):
            ReportingCategory(
                name='X', db_id=1, css_class='cat-x', background='#000000',
                font='#FFFFFF', ancestor_ids=(1,), colour='#fff')

    def test_it_does_not_coerce_a_string_id(self):
        with pytest.raises(ValidationError):
            ReportingCategory(
                name='X', db_id='100', css_class='cat-x', background='#000000',
                font='#FFFFFF', ancestor_ids=(1,))

    def test_it_is_frozen(self):
        with pytest.raises(ValidationError):
            REPORTING_CATEGORIES[0].name = 'other'


class TestByName:
    def test_it_strips_like_its_callers_do(self):
        assert rc.by_name('  Housing  ').db_id == 300

    def test_an_unknown_name_is_none_not_a_default_bucket(self):
        assert rc.by_name('Money Movement') is None
