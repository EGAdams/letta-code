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
from category_taxonomy_seed import LEGACY_TAXONOMY

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


def test_pre_004_tree_shows_the_walgreens_misattribution(taxonomy):
    """The fixture models the tree as it stood BEFORE migration 004, where
    378 -> 241 -> 240 -> (pointer) 242 silently made Rosemary's pharmacy spend
    Robert's. Kept as a regression witness: migration 004 repointed 240 at the
    unassigned bucket 418 and moved 378 under it, and
    test_unassigned_medical_is_per_expense_only in test_category_taxonomy.py
    pins the post-004 behaviour."""
    assert server._reporting_category_for_id(WALGREENS) == \
        "Robert Benefits and Medical"


def test_taxonomy_composition_root_is_memoized(monkeypatch):
    monkeypatch.setattr(server, "_category_taxonomy", None)
    first = server._get_category_taxonomy()
    assert server._get_category_taxonomy() is first


# ── Set Category dialog list ─────────────────────────────────────────────
def _dialog_names(monkeypatch, taxonomy):
    monkeypatch.setattr(server, "_get_category_taxonomy", lambda: taxonomy)
    return [c["name"] for c in server._rol_finance_categories()]


def test_dialog_lists_db_categories_and_one_uncategorized(monkeypatch):
    tree = StaticCategoryTaxonomy([
        CategoryNode(id=GIFTS, parent_id=None, name="Gifts & Love Offerings",
                     is_report_category=True, is_selectable=True,
                     display_order=1, report_label="Gifts & Love Offerings",
                     report_bg=GREEN, report_fg="#000000",
                     css_class="cat-gifts-and-love-offerings"),
        CategoryNode(id=402, parent_id=None, name="Money Movement",
                     is_report_category=True, is_selectable=True,
                     display_order=2,
                     report_label="Money Movement — Not an Expense",
                     report_bg="#D6DCE4", report_fg="#000000",
                     css_class="cat-money-movement",
                     excluded_from_nonprofit_totals=True),
    ])
    names = _dialog_names(monkeypatch, tree)
    assert names == ["Gifts & Love Offerings",
                     "Money Movement — Not an Expense", "Uncategorized"]


def test_dialog_does_not_duplicate_uncategorized_in_fallback(monkeypatch):
    """LEGACY_TAXONOMY lists Uncategorized as selectable; appending the sentinel
    unconditionally showed it twice whenever the DB was unreachable."""
    names = _dialog_names(monkeypatch, LEGACY_TAXONOMY)
    assert names.count("Uncategorized") == 1


def test_dialog_flags_categories_excluded_from_totals(monkeypatch):
    monkeypatch.setattr(server, "_get_category_taxonomy", lambda: LEGACY_TAXONOMY)
    by_name = {c["name"]: c for c in server._rol_finance_categories()}
    assert by_name["Personal"]["excluded"] is True
    assert by_name["Gifts & Love Offerings"]["excluded"] is False


def test_writer_accepts_every_category_the_dialog_offers(monkeypatch):
    """The dialog must never offer something recategorize_expense rejects."""
    monkeypatch.setattr(server, "_get_category_taxonomy", lambda: LEGACY_TAXONOMY)
    for entry in server._rol_finance_categories():
        _target_id, css = server._resolve_reporting_category(entry["name"])
        assert css is not None, f"writer would reject {entry['name']!r}"


def test_writer_rejects_an_unknown_category(monkeypatch):
    monkeypatch.setattr(server, "_get_category_taxonomy", lambda: LEGACY_TAXONOMY)
    assert server._resolve_reporting_category("Nonsense") == (None, None)


def test_uncategorized_clears_the_category_id(monkeypatch):
    monkeypatch.setattr(server, "_get_category_taxonomy", lambda: LEGACY_TAXONOMY)
    assert server._resolve_reporting_category("Uncategorized") == \
        (None, "cat-uncategorized")


# ── the picker template must never reach the browser unrendered ──────────
def test_receipt_only_picker_has_a_populated_category_list(monkeypatch):
    """CATEGORY_PICKER_HTML is a template: its CATS array and colour rules are
    placeholders. Returning it raw shipped `var CATS = []` to the browser and
    the Set Category dialog rendered with no categories."""
    monkeypatch.setattr(server, "_get_category_taxonomy", lambda: LEGACY_TAXONOMY)
    _css, html, _row_css = server._receipt_only_picker_assets()
    assert "__ROL_CATS__" not in html, "picker template left unrendered"
    assert "__ROL_CAT_CSS__" not in html
    assert "var CATS = [];" not in html and "var CATS = []" not in html
    assert "Gifts & Love Offerings" in html
    assert ".cat-gifts-and-love-offerings {" in html


def test_report_picker_refresh_does_not_call_back_into_this_server(monkeypatch):
    """add_category_picker fetches categories over HTTP when none are passed —
    from this very process, inside one of its own request handlers. The server
    must always hand its in-process list in."""
    monkeypatch.setattr(server, "_get_category_taxonomy", lambda: LEGACY_TAXONOMY)
    calls = []

    class _Spy:
        CATEGORY_PICKER_CSS = ""
        CLICKABLE_ROW_CSS = ""

        def add_category_picker(self, html, categories=None):
            calls.append(categories)
            return html

        def load_picker_categories(self, *a, **k):
            raise AssertionError("server must not HTTP-fetch its own categories")

    monkeypatch.setattr(server, "_picker_module", lambda: _Spy())
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as handle:
        handle.write("<html></html>")
        path = handle.name
    server._report_html_with_current_picker(path)
    assert calls and calls[0], "categories were not passed in"
