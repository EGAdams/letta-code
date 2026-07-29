"""Tests for the category taxonomy port.

Facts here were read off the live `nonprofit_finance` DB on 2026-07-28 (169
categories, 1041 expenses). The two ids most often quoted in tickets are both
wrong in the wild and are pinned here on purpose:

    192 is "Individuals",              Guest Speakers is 204
    210 is "Ministries & Organizations", Right to Life is 218

Both real leaves are descendants of 190 Gifts & Love Offerings, so both must
roll up green while keeping their own id for SQL drill-down.
"""

from __future__ import annotations

import pytest

from category_taxonomy import (
    CategoryNode,
    FallbackCategoryTaxonomy,
    ICategoryTaxonomy,
    MySqlCategoryTaxonomy,
    StaticCategoryTaxonomy,
)
from category_taxonomy_seed import LEGACY_TAXONOMY

GREEN = "#A9D18E"
GIFTS = 190
GUEST_SPEAKERS = 204
RIGHT_TO_LIFE = 218


def _tree(*nodes: CategoryNode) -> StaticCategoryTaxonomy:
    return StaticCategoryTaxonomy(nodes)


@pytest.fixture
def gifts_tree() -> StaticCategoryTaxonomy:
    """The real 190 subtree as it exists in the database."""
    return _tree(
        CategoryNode(
            id=GIFTS, parent_id=1, name="Gifts & Love Offerings",
            is_report_category=True, is_selectable=True, display_order=10,
            report_label="Gifts & Love Offerings", report_bg=GREEN,
            report_fg="#000000", css_class="cat-gifts-and-love-offerings",
            functional_class="PROGRAM",
        ),
        CategoryNode(id=1, parent_id=None, name="Church"),
        CategoryNode(id=192, parent_id=GIFTS, name="Individuals",
                     irs_natural_class="Grants to domestic individuals"),
        CategoryNode(id=GUEST_SPEAKERS, parent_id=192, name="Guest Speakers",
                     irs_natural_class="Grants to domestic individuals"),
        CategoryNode(id=210, parent_id=GIFTS, name="Ministries & Organizations",
                     irs_natural_class="Grants to domestic organizations"),
        CategoryNode(id=RIGHT_TO_LIFE, parent_id=210, name="Right to Life",
                     irs_natural_class="Grants to domestic organizations"),
    )


# ── the two ids everyone gets wrong ──────────────────────────────────────
def test_right_to_life_is_218_not_210(gifts_tree: ICategoryTaxonomy):
    assert gifts_tree.get(210).name == "Ministries & Organizations"
    assert gifts_tree.get(RIGHT_TO_LIFE).name == "Right to Life"


def test_guest_speakers_is_204_not_192(gifts_tree: ICategoryTaxonomy):
    assert gifts_tree.get(192).name == "Individuals"
    assert gifts_tree.get(GUEST_SPEAKERS).name == "Guest Speakers"


@pytest.mark.parametrize("leaf_id", [RIGHT_TO_LIFE, GUEST_SPEAKERS])
def test_gift_leaves_roll_up_to_gifts_in_green(gifts_tree, leaf_id):
    bucket = gifts_tree.report_category_for(leaf_id)
    assert bucket.id == GIFTS
    assert bucket.label == "Gifts & Love Offerings"
    assert gifts_tree.style_for(leaf_id).background == GREEN
    assert gifts_tree.css_class_for(leaf_id) == "cat-gifts-and-love-offerings"


@pytest.mark.parametrize("leaf_id", [RIGHT_TO_LIFE, GUEST_SPEAKERS])
def test_leaf_id_survives_rollup(gifts_tree, leaf_id):
    """The whole point: reporting under the parent must not overwrite the leaf."""
    assert gifts_tree.report_category_for(leaf_id).id == GIFTS
    assert gifts_tree.get(leaf_id).id == leaf_id
    assert gifts_tree.is_descendant(leaf_id, GIFTS)


def test_irs_class_distinguishes_leaves_sharing_one_green_bucket(gifts_tree):
    """Individuals vs organizations are IRS-distinct even though both are green."""
    assert gifts_tree.report_category_for(GUEST_SPEAKERS).id == \
        gifts_tree.report_category_for(RIGHT_TO_LIFE).id
    assert gifts_tree.get(GUEST_SPEAKERS).irs_natural_class != \
        gifts_tree.get(RIGHT_TO_LIFE).irs_natural_class


def test_drilldown_lists_only_that_leaf(gifts_tree):
    leaves = {n.id for n in gifts_tree.leaves_under(GIFTS)}
    assert leaves == {GUEST_SPEAKERS, RIGHT_TO_LIFE}
    assert {n.id for n in gifts_tree.leaves_under(210)} == {RIGHT_TO_LIFE}


# ── the Robert/Rosemary misattribution ───────────────────────────────────
@pytest.fixture
def medical_tree() -> StaticCategoryTaxonomy:
    """The 240 subtree as it will exist after migration 003/004: per-person
    report buckets, plus 418 for the 32 expenses whose bank line names nobody."""
    def bucket(node_id, name, colour, order):
        return CategoryNode(
            id=node_id, parent_id=241, name=name, is_report_category=True,
            is_selectable=True, display_order=order, report_label=name,
            report_bg=colour, report_fg="#000000",
            css_class=f"cat-{name.lower().replace(' ', '-').replace('—', '')}",
        )
    return _tree(
        CategoryNode(id=240, parent_id=1, name="Staff & Benefits"),
        CategoryNode(id=241, parent_id=240, name="Senior Pastors"),
        bucket(414, "Robert Benefits & Medical", "#CCC0DA", 20),
        bucket(415, "Rosemary Benefits & Medical", "#F4B6C2", 21),
        CategoryNode(
            id=418, parent_id=241, name="Senior Pastors Medical — Unassigned",
            is_report_category=True, is_selectable=True, display_order=22,
            report_label="Senior Pastors Medical — Unassigned",
            report_bg="#E6D5E8", report_fg="#000000",
            css_class="cat-senior-pastors-medical-unassigned",
            per_expense_only=True,
        ),
        CategoryNode(id=242, parent_id=414, name="RJ — Priority Health"),
        CategoryNode(id=243, parent_id=415, name="RM — Priority Health"),
        CategoryNode(id=378, parent_id=418, name="Walgreens"),
        CategoryNode(id=365, parent_id=418, name="Dental"),
    )


def test_priority_health_leaves_report_under_the_right_person(medical_tree):
    assert medical_tree.report_category_for(242).id == 414
    assert medical_tree.report_category_for(243).id == 415


def test_walgreens_is_not_silently_attributed_to_robert(medical_tree):
    """Live bug: 378 falls through to 240 and defaults to Robert, moving ~32
    expenses (~$2.1k) into the wrong person's total with no marker."""
    bucket = medical_tree.report_category_for(378)
    assert bucket.id == 418
    assert bucket.id not in (414, 415)


@pytest.mark.parametrize("leaf_id", [378, 365])
def test_unassigned_medical_is_per_expense_only(medical_tree, leaf_id):
    """Reassigning one Walgreens row to Rosemary must not repoint the vendor
    mapping for every other Walgreens row."""
    assert medical_tree.report_category_for(leaf_id).per_expense_only is True


# ── report/accounting axes are independent ───────────────────────────────
def test_vehicle_insurance_reports_as_insurance_but_classifies_as_travel():
    tree = _tree(
        CategoryNode(id=1, parent_id=None, name="Church"),
        CategoryNode(
            id=230, parent_id=1, name="Insurance", is_report_category=True,
            is_selectable=True, report_label="Insurance, Taxes & Fees",
            report_bg="#FCD5B4", report_fg="#000000",
            css_class="cat-insurance-taxes-and-fees",
            irs_natural_class="Insurance",
        ),
        CategoryNode(id=233, parent_id=230, name="Vehicles",
                     irs_natural_class="Travel"),
    )
    assert tree.report_category_for(233).label == "Insurance, Taxes & Fees"
    assert tree.get(233).irs_natural_class == "Travel"


def test_personal_is_excluded_from_nonprofit_totals():
    tree = _tree(
        CategoryNode(
            id=3, parent_id=None, name="Personal", is_report_category=True,
            is_selectable=True,
            report_label="Personal / Non-Church — Review Required",
            report_bg="#948A54", report_fg="#FFFFFF", css_class="cat-personal",
            functional_class="NON_CHURCH", excluded_from_nonprofit_totals=True,
        ),
        CategoryNode(id=999, parent_id=3, name="Some personal vendor"),
    )
    assert tree.is_excluded_from_nonprofit_totals(3)
    assert tree.is_excluded_from_nonprofit_totals(999), "must inherit down the tree"
    assert not tree.is_excluded_from_nonprofit_totals(None)


# ── uncategorized + robustness ───────────────────────────────────────────
def test_unknown_and_null_ids_are_uncategorized(gifts_tree):
    for unknown in (None, 999_999):
        assert gifts_tree.report_category_for(unknown) is None
        assert gifts_tree.label_for(unknown) == "Uncategorized"
        assert gifts_tree.css_class_for(unknown) == "cat-uncategorized"


def test_parent_cycle_does_not_hang():
    tree = _tree(
        CategoryNode(id=10, parent_id=11, name="a"),
        CategoryNode(id=11, parent_id=10, name="b"),
    )
    assert tree.report_category_for(10) is None
    assert tree.is_descendant(10, 11)


def test_pointer_cycle_does_not_hang():
    tree = _tree(
        CategoryNode(id=20, parent_id=None, name="a", report_category_id=21),
        CategoryNode(id=21, parent_id=None, name="b", report_category_id=20),
    )
    assert tree.report_category_for(20) is None


def test_selectable_list_is_ordered_and_excludes_non_report_nodes(gifts_tree):
    selectable = gifts_tree.selectable_report_categories()
    assert [n.id for n in selectable] == [GIFTS]
    assert all(n.is_report_category and n.is_active for n in selectable)


def test_inactive_report_category_is_not_selectable():
    tree = _tree(CategoryNode(
        id=362, parent_id=330, name="AOL Search and Recovery",
        is_active=False, is_report_category=True, is_selectable=True,
    ))
    assert tree.selectable_report_categories() == ()


# ── the legacy seed must reproduce the old maps exactly ──────────────────
# Verbatim copies of server.py's dicts. If phase 3 changed behaviour, these
# fail — which is the entire safety argument for shipping the port first.
_LEGACY_ANCESTOR_MAP = {
    100: "Church Facility", 110: "Church Facility", 120: "Church Utilities",
    130: "Food & Hospitality", 140: "Office & Administration",
    150: "Ministry and Worship", 160: "Travel & Vehicle",
    190: "Gifts & Love Offerings", 230: "Insurance, Taxes & Fees",
    240: "Robert Benefits and Medical", 242: "Robert Benefits and Medical",
    243: "Rosemary Benefits & Medical", 300: "Housing", 310: "Housing",
    320: "Housing", 330: "Housing", 340: "Housing", 350: "Housing",
    358: "Insurance, Taxes & Fees", 364: "Uncategorized",
    400: "Insurance, Taxes & Fees", 1: "Uncategorized", 2: "Housing",
    3: "Personal",
}
_LEGACY_STYLE = {
    "Church Facility": ("#B8CCE4", "#000000"),
    "Church Utilities": ("#95B3D7", "#000000"),
    "Ministry and Worship": ("#DCE6F1", "#000000"),
    "Office & Administration": ("#4F81BD", "#FFFFFF"),
    "Food & Hospitality": ("#F4F199", "#000000"),
    "Gifts & Love Offerings": ("#A9D18E", "#000000"),
    "Robert Benefits and Medical": ("#CCC0DA", "#000000"),
    "Rosemary Benefits & Medical": ("#F4B6C2", "#000000"),
    "Travel & Vehicle": ("#F4B683", "#000000"),
    "Insurance, Taxes & Fees": ("#FCD5B4", "#000000"),
    "Housing": ("#DDD9C4", "#000000"),
    "Personal": ("#948A54", "#FFFFFF"),
    "Uncategorized": ("#BFBFBF", "#000000"),
}
_LEGACY_DB_MAP = {
    "Church Facility": 100, "Church Utilities": 120,
    "Ministry and Worship": 150, "Office & Administration": 140,
    "Food & Hospitality": 130, "Gifts & Love Offerings": 190,
    "Robert Benefits and Medical": 242, "Rosemary Benefits & Medical": 243,
    "Travel & Vehicle": 160, "Insurance, Taxes & Fees": 230,
    "Housing": 300, "Personal": 3, "Uncategorized": None,
}


@pytest.mark.parametrize("category_id,expected", sorted(_LEGACY_ANCESTOR_MAP.items()))
def test_legacy_seed_reproduces_ancestor_map(category_id, expected):
    assert LEGACY_TAXONOMY.label_for(category_id) == expected


@pytest.mark.parametrize("category_id,expected", sorted(_LEGACY_ANCESTOR_MAP.items()))
def test_legacy_seed_reproduces_styles(category_id, expected):
    background, font = _LEGACY_STYLE[expected]
    style = LEGACY_TAXONOMY.style_for(category_id)
    assert (style.background, style.font) == (background, font)


def test_legacy_seed_reproduces_db_map_and_dialog_order():
    selectable = LEGACY_TAXONOMY.selectable_report_categories()
    assert [n.label for n in selectable] == list(_LEGACY_DB_MAP)
    for node in selectable:
        expected_id = _LEGACY_DB_MAP[node.label]
        if expected_id is not None:
            assert node.id == expected_id


def test_legacy_seed_marks_personal_excluded():
    assert LEGACY_TAXONOMY.is_excluded_from_nonprofit_totals(3)


# ── the MySQL adapter ────────────────────────────────────────────────────
class _FakeCursor:
    def __init__(self, columns, rows):
        self._columns, self._rows = columns, rows
        self._result = []
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append(sql)
        if "INFORMATION_SCHEMA.COLUMNS" in sql:
            self._result = [{"COLUMN_NAME": c} for c in self._columns]
        else:
            self._result = self._rows

    def fetchall(self):
        return self._result

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _factory(columns, rows, calls=None):
    def make():
        if calls is not None:
            calls.append(1)
        return _FakeConnection(_FakeCursor(columns, rows))
    return make


_MIGRATED_COLUMNS = [
    "id", "parent_id", "name", "is_active", "is_report_category",
    "is_selectable", "display_order", "report_label", "report_bg",
    "report_fg", "css_class", "report_category_id", "irs_natural_class",
    "functional_class", "excluded_from_nonprofit_totals", "per_expense_only",
]


def test_mysql_adapter_reads_migrated_columns():
    rows = [
        {"id": 190, "parent_id": 1, "name": "Gifts & Love Offerings",
         "is_active": 1, "is_report_category": 1, "is_selectable": 1,
         "display_order": 10, "report_label": "Gifts & Love Offerings",
         "report_bg": GREEN, "report_fg": "#000000",
         "css_class": "cat-gifts-and-love-offerings", "report_category_id": None,
         "irs_natural_class": None, "functional_class": "PROGRAM",
         "excluded_from_nonprofit_totals": 0, "per_expense_only": 0},
        {"id": 218, "parent_id": 190, "name": "Right to Life", "is_active": 1,
         "is_report_category": 0, "is_selectable": 0, "display_order": 0,
         "report_label": None, "report_bg": None, "report_fg": None,
         "css_class": None, "report_category_id": None,
         "irs_natural_class": None, "functional_class": None,
         "excluded_from_nonprofit_totals": 0, "per_expense_only": 0},
    ]
    taxonomy = MySqlCategoryTaxonomy(_factory(_MIGRATED_COLUMNS, rows))
    assert taxonomy.report_category_for(218).id == 190
    assert taxonomy.style_for(218).background == GREEN


def test_mysql_adapter_raises_when_db_is_down():
    """The adapter is a pure adapter; resilience is the decorator's job."""
    def exploding():
        raise RuntimeError("db down")
    with pytest.raises(RuntimeError):
        MySqlCategoryTaxonomy(exploding).label_for(190)


def test_mysql_adapter_caches_and_invalidates():
    calls: list[int] = []
    rows = [{"id": 190, "parent_id": None, "name": "G", "is_active": 1,
             "is_report_category": 1, "is_selectable": 1, "display_order": 0,
             "report_label": "G", "report_bg": GREEN, "report_fg": "#000000",
             "css_class": "cat-g", "report_category_id": None,
             "irs_natural_class": None, "functional_class": None,
             "excluded_from_nonprofit_totals": 0, "per_expense_only": 0}]
    taxonomy = MySqlCategoryTaxonomy(
        _factory(_MIGRATED_COLUMNS, rows, calls), ttl_seconds=300)
    taxonomy.get(190)
    taxonomy.get(190)
    assert len(calls) == 1
    taxonomy.invalidate()
    taxonomy.get(190)
    assert len(calls) == 2


# ── the fallback decorator ───────────────────────────────────────────────
def test_fallback_used_when_primary_raises():
    def exploding():
        raise RuntimeError("db down")
    taxonomy = FallbackCategoryTaxonomy(
        MySqlCategoryTaxonomy(exploding), LEGACY_TAXONOMY)
    assert taxonomy.label_for(GIFTS) == "Gifts & Love Offerings"
    assert taxonomy.selectable_report_categories(), "dialog must never empty"


def test_fallback_used_when_primary_does_not_know_the_id():
    """The regression that broke test_server.py: a primary wired to a stubbed
    connection answered "Uncategorized" for every id, and that empty answer
    looked authoritative. An id the primary cannot resolve must defer."""
    rows = [{"id": 999, "parent_id": None, "name": "unrelated", "is_active": 1,
             "is_report_category": 0, "is_selectable": 0, "display_order": 0,
             "report_label": None, "report_bg": None, "report_fg": None,
             "css_class": None, "report_category_id": None,
             "irs_natural_class": None, "functional_class": None,
             "excluded_from_nonprofit_totals": 0, "per_expense_only": 0}]
    taxonomy = FallbackCategoryTaxonomy(
        MySqlCategoryTaxonomy(_factory(_MIGRATED_COLUMNS, rows)), LEGACY_TAXONOMY)
    assert taxonomy.label_for(GIFTS) == "Gifts & Love Offerings"


def test_fallback_prefers_the_primary_when_it_answers():
    rows = [{"id": GIFTS, "parent_id": None, "name": "Gifts & Love Offerings",
             "is_active": 1, "is_report_category": 1, "is_selectable": 1,
             "display_order": 0, "report_label": "RENAMED IN DB",
             "report_bg": GREEN, "report_fg": "#000000", "css_class": "cat-g",
             "report_category_id": None, "irs_natural_class": None,
             "functional_class": None, "excluded_from_nonprofit_totals": 0,
             "per_expense_only": 0}]
    taxonomy = FallbackCategoryTaxonomy(
        MySqlCategoryTaxonomy(_factory(_MIGRATED_COLUMNS, rows)), LEGACY_TAXONOMY)
    assert taxonomy.label_for(GIFTS) == "RENAMED IN DB"


def test_fallback_invalidate_reaches_the_primary():
    calls: list[int] = []
    rows = [{"id": GIFTS, "parent_id": None, "name": "G", "is_active": 1,
             "is_report_category": 1, "is_selectable": 1, "display_order": 0,
             "report_label": "G", "report_bg": GREEN, "report_fg": "#000000",
             "css_class": "cat-g", "report_category_id": None,
             "irs_natural_class": None, "functional_class": None,
             "excluded_from_nonprofit_totals": 0, "per_expense_only": 0}]
    taxonomy = FallbackCategoryTaxonomy(
        MySqlCategoryTaxonomy(_factory(_MIGRATED_COLUMNS, rows, calls), ttl_seconds=300),
        LEGACY_TAXONOMY)
    taxonomy.get(GIFTS)
    taxonomy.get(GIFTS)
    assert len(calls) == 1
    taxonomy.invalidate()
    taxonomy.get(GIFTS)
    assert len(calls) == 2
