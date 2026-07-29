"""server.py must resolve report buckets through ICategoryTaxonomy.

The regression these pin: `recategorize_expense` computed
`previous_reporting_category` with a flat `REPORTING_CATEGORY_ANCESTOR_MAP.get()`
that covers 24 of 169 categories. Every expense stored on any other id — 280 of
892 categorised rows on the live DB (2026-07-28) — was recorded as
"Uncategorized", so pressing Undo repainted the row grey instead of restoring
its real bucket colour.
"""

from __future__ import annotations

import pytest

import server
from category_taxonomy import CategoryNode, StaticCategoryTaxonomy

GREEN = "#A9D18E"
GIFTS = 190
RIGHT_TO_LIFE = 218
GUEST_SPEAKERS = 204
WALGREENS = 378


@pytest.fixture
def taxonomy(monkeypatch) -> StaticCategoryTaxonomy:
    """The real subtrees these ids live in, with the legacy presentation."""
    tree = StaticCategoryTaxonomy([
        CategoryNode(id=1, parent_id=None, name="Church",
                     is_report_category=True, report_label="Uncategorized",
                     report_bg="#BFBFBF", report_fg="#000000",
                     css_class="cat-uncategorized"),
        CategoryNode(
            id=GIFTS, parent_id=1, name="Gifts & Love Offerings",
            is_report_category=True, is_selectable=True, display_order=5,
            report_label="Gifts & Love Offerings", report_bg=GREEN,
            report_fg="#000000", css_class="cat-gifts-and-love-offerings"),
        CategoryNode(id=192, parent_id=GIFTS, name="Individuals"),
        CategoryNode(id=GUEST_SPEAKERS, parent_id=192, name="Guest Speakers"),
        CategoryNode(id=210, parent_id=GIFTS, name="Ministries & Organizations"),
        CategoryNode(id=RIGHT_TO_LIFE, parent_id=210, name="Right to Life"),
        CategoryNode(id=240, parent_id=1, name="Staff & Benefits",
                     report_category_id=242),
        CategoryNode(id=241, parent_id=240, name="Senior Pastors"),
        CategoryNode(
            id=242, parent_id=241, name="RJ — Priority Health",
            is_report_category=True, is_selectable=True, display_order=6,
            report_label="Robert Benefits and Medical", report_bg="#CCC0DA",
            report_fg="#000000", css_class="cat-robert-benefits-and-medical"),
        CategoryNode(id=WALGREENS, parent_id=241, name="Walgreens"),
    ])
    monkeypatch.setattr(server, "_get_category_taxonomy", lambda: tree)
    return tree


@pytest.mark.parametrize("leaf_id", [RIGHT_TO_LIFE, GUEST_SPEAKERS])
def test_leaf_rolls_up_to_gifts(taxonomy, leaf_id):
    assert server._reporting_category_for_id(leaf_id) == "Gifts & Love Offerings"


def test_rollup_ignores_the_legacy_parent_of_argument(taxonomy):
    """Callers still pass a prebuilt parent map; it must not change the answer."""
    assert server._reporting_category_for_id(RIGHT_TO_LIFE, {}) == \
        server._reporting_category_for_id(RIGHT_TO_LIFE)


def test_flat_map_would_have_said_uncategorized(taxonomy):
    """Guards the fix: if someone reinstates the flat lookup, this fails."""
    assert server.REPORTING_CATEGORY_ANCESTOR_MAP.get(RIGHT_TO_LIFE) is None
    assert server._reporting_category_for_id(RIGHT_TO_LIFE) != "Uncategorized"


def test_unknown_and_null_ids_remain_uncategorized(taxonomy):
    assert server._reporting_category_for_id(None) == "Uncategorized"
    assert server._reporting_category_for_id(999_999) == "Uncategorized"


def test_legacy_bucket_ids_are_unchanged(taxonomy):
    """The 24 ids the flat map did cover must keep their old answers."""
    assert server._reporting_category_for_id(GIFTS) == "Gifts & Love Offerings"
    assert server._reporting_category_for_id(242) == "Robert Benefits and Medical"


def test_walgreens_still_reports_as_robert_until_migration_004(taxonomy):
    """Documents the live misattribution rather than silently fixing it here:
    378 -> 241 -> 240 -> (pointer) 242. Migration 003/004 moves it to the
    unassigned bucket 418; until then this is the honest current answer."""
    assert server._reporting_category_for_id(WALGREENS) == \
        "Robert Benefits and Medical"


def test_taxonomy_composition_root_is_memoized(monkeypatch):
    monkeypatch.setattr(server, "_category_taxonomy", None)
    first = server._get_category_taxonomy()
    assert server._get_category_taxonomy() is first
