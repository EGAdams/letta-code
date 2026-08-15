"""The legacy hardcoded report maps, expressed as a `CategoryNode` snapshot.

This exists so the taxonomy port can ship **without changing any behaviour**:
`LEGACY_TAXONOMY` reproduces `REPORTING_CATEGORY_ANCESTOR_MAP` /
`REPORTING_CATEGORY_CLASS` / `REPORTING_CATEGORY_STYLE` /
`REPORTING_CATEGORY_DB_MAP` exactly, including their irregularities, and
`test_category_taxonomy.py` asserts that equivalence ID by ID.

It keeps two jobs afterwards:
  * offline fallback for `MySqlCategoryTaxonomy` when the DB is unreachable;
  * the presentation source until migration 002 backfills the real columns.

Known irregularities preserved verbatim (they are bugs to fix in phases 5-6,
not to fix here — a seed that "improves" on the legacy maps would make the
equivalence test meaningless):
  * 110 Facility Upkeep reports as "Church Facility" (Payment), merging two
    distinct buckets the new dialog splits.
  * 240 Staff & Benefits defaults to Robert, misattributing Rosemary's spend.
  * 358 / 400 municipal payees report as "Insurance, Taxes & Fees".
  * 150 "Education / Music / TV" is labelled "Ministry and Worship".
"""

from __future__ import annotations

from category_taxonomy import CategoryNode, StaticCategoryTaxonomy

# name -> (background, font, css class) — the three legacy presentation dicts
# collapsed into one row per bucket.
_LEGACY_BUCKETS: dict[str, tuple[str, str, str]] = {
    "Church Facility": ("#B8CCE4", "#000000", "cat-church-facility"),
    "Church Utilities": ("#95B3D7", "#000000", "cat-church-utilities"),
    "Ministry and Worship": ("#DCE6F1", "#000000", "cat-ministry-and-worship"),
    "Office & Administration": ("#4F81BD", "#FFFFFF", "cat-office-and-administration"),
    "Food & Hospitality": ("#F4F199", "#000000", "cat-food-and-hospitality"),
    "Gifts & Love Offerings": ("#A9D18E", "#000000", "cat-gifts-and-love-offerings"),
    "Robert Benefits and Medical": (
        "#CCC0DA", "#000000", "cat-robert-benefits-and-medical"),
    "Rosemary Benefits & Medical": (
        "#F4B6C2", "#000000", "cat-rosemary-benefits-and-medical"),
    "Travel & Vehicle": ("#F4B683", "#000000", "cat-travel-and-vehicle"),
    "Insurance, Taxes & Fees": ("#FCD5B4", "#000000", "cat-insurance-taxes-and-fees"),
    "Housing": ("#DDD9C4", "#000000", "cat-housing"),
    "Personal": ("#948A54", "#FFFFFF", "cat-personal"),
    "Uncategorized": ("#BFBFBF", "#000000", "cat-uncategorized"),
}

# The representative id each bucket wrote back (REPORTING_CATEGORY_DB_MAP), in
# the dialog order the legacy REPORTING_CATEGORY_CLASS dict iterated in.
_LEGACY_BUCKET_IDS: tuple[tuple[str, int | None], ...] = (
    ("Church Facility", 100),
    ("Church Utilities", 120),
    ("Ministry and Worship", 150),
    ("Office & Administration", 140),
    ("Food & Hospitality", 130),
    ("Gifts & Love Offerings", 190),
    ("Robert Benefits and Medical", 242),
    ("Rosemary Benefits & Medical", 243),
    ("Travel & Vehicle", 160),
    ("Insurance, Taxes & Fees", 230),
    ("Housing", 300),
    ("Personal", 3),
    ("Uncategorized", None),
)

# Every non-representative id from REPORTING_CATEGORY_ANCESTOR_MAP, pointed at
# the representative id of the bucket it resolved to.
_LEGACY_POINTERS: dict[int, int] = {
    110: 100,
    240: 242,
    2: 300, 310: 300, 320: 300, 330: 300, 340: 300, 350: 300,
    358: 230, 400: 230,
    1: 1, 364: 1,
}

# "Uncategorized" has no DB id of its own; 1 (Church) and 364 (Electronic
# Payment) are the two ids the legacy map resolved to it.
_UNCATEGORIZED_NODE_ID = 1


def _build_legacy_nodes() -> list[CategoryNode]:
    nodes: list[CategoryNode] = []
    for order, (label, category_id) in enumerate(_LEGACY_BUCKET_IDS):
        background, font, css_class = _LEGACY_BUCKETS[label]
        node_id = _UNCATEGORIZED_NODE_ID if category_id is None else category_id
        nodes.append(CategoryNode(
            id=node_id,
            parent_id=None,
            name=label,
            is_report_category=True,
            is_selectable=True,
            display_order=order,
            report_label=label,
            report_bg=background,
            report_fg=font,
            css_class=css_class,
            excluded_from_nonprofit_totals=(label == "Personal"),
        ))
    known = {n.id for n in nodes}
    for source_id, target_id in _LEGACY_POINTERS.items():
        if source_id in known:
            continue
        nodes.append(CategoryNode(
            id=source_id,
            parent_id=None,
            name=f"legacy-alias-{source_id}",
            report_category_id=target_id,
        ))
    return nodes


LEGACY_TAXONOMY = StaticCategoryTaxonomy(_build_legacy_nodes())
