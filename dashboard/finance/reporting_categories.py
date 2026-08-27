"""The thirteen reporting buckets, as one typed list the four legacy maps derive from.

`server.py` used to carry four hand-maintained dicts — `REPORTING_CATEGORY_DB_MAP`,
`REPORTING_CATEGORY_CLASS`, `REPORTING_CATEGORY_STYLE` (all keyed by bucket name)
and `REPORTING_CATEGORY_ANCESTOR_MAP` (keyed by the ids the first one hands out).
Nothing checked that they agreed. Adding a bucket to one and forgetting another
produced a report row with no CSS class or no colour — rendered, served, and
indistinguishable from a styling choice.

Here there is one `ReportingCategory` per bucket and the four dicts are derived
views, so a half-added bucket is not expressible.

**These maps are a fallback, not the live source.** Reads go through
`ICategoryTaxonomy` (`category_taxonomy.py`), which sources buckets from the
`categories` table's `is_report_category` / `report_category_id` columns.
`server.py` consults `CLASS`/`DB_MAP` only when the taxonomy cannot resolve a
name — a stale client, or a `report.html` injected before the taxonomy landed.
`STYLE` and `ANCESTOR_MAP` have no production reader left at all; they stay as
the documented shape of the legacy behaviour.

So the validation added here **defends** a fallback path rather than fixing a
live defect (plan rule 11). `category_taxonomy_seed.py` deliberately restates
the same values a second time and is *not* derived from this list: its job is to
be an independent restatement that `tests/test_category_taxonomy.py` pins id by
id, and deriving it would make that equivalence test tautological.
"""

from __future__ import annotations

from pydantic import field_validator, model_validator

from contracts import StrictModel


class ReportingCategory(StrictModel):
    """One reporting bucket: its name, the id it writes back, and how it renders.

    Every field is required. Each one's absence is a silent defect rather than a
    loud one:

    * `db_id` — the representative `categories.id` a dialog pick writes back.
      `None` is meaningful (it clears `category_id`), so this is `int | None`
      declared required, not an optional field with a `None` default: a bucket
      that forgot to say which id it writes is not the same as one that
      deliberately clears it.
    * `css_class` — report rows bake this into the `<tr>` on disk. Missing, the
      row renders unstyled and looks like a styling choice.
    * `background` / `font` — the synthetic "Receipt Only" rows are coloured
      inline from these.
    * `ancestor_ids` — every `categories.id` that rolls up into this bucket,
      including `db_id` itself.
    """

    name: str
    db_id: int | None
    css_class: str
    background: str
    font: str
    ancestor_ids: tuple[int, ...]

    @field_validator('name', 'css_class')
    @classmethod
    def _not_blank(cls, value: str) -> str:
        # min_length=1 is not "not blank" when the consumer strips (plan rule 10).
        if not value.strip():
            raise ValueError('must not be blank')
        return value

    @field_validator('background', 'font')
    @classmethod
    def _is_hex_colour(cls, value: str) -> str:
        if len(value) != 7 or not value.startswith('#'):
            raise ValueError(f'{value!r} is not a #RRGGBB colour')
        int(value[1:], 16)  # raises ValueError on a non-hex body
        return value

    @model_validator(mode='after')
    def _representative_id_rolls_up_to_itself(self) -> ReportingCategory:
        if not self.ancestor_ids:
            raise ValueError(f'{self.name!r} has no ancestor ids')
        if self.db_id is not None and self.db_id not in self.ancestor_ids:
            raise ValueError(
                f'{self.name!r} writes back id {self.db_id} but that id does not '
                'roll up to it — the picker would write a category the report '
                'then attributes to a different bucket')
        return self


# Declaration order is the order the legacy `REPORTING_CATEGORY_CLASS` dict
# iterated in, which is the Set Category dialog's display order. Keep it.
REPORTING_CATEGORIES: tuple[ReportingCategory, ...] = (
    ReportingCategory(
        name='Church Facility', db_id=100, css_class='cat-church-facility',
        background='#B8CCE4', font='#000000',
        # 110 Facility Upkeep reports here too — a legacy merge of two buckets
        # the current dialog splits. Preserved deliberately.
        ancestor_ids=(100, 110)),
    ReportingCategory(
        name='Church Utilities', db_id=120, css_class='cat-church-utilities',
        background='#95B3D7', font='#000000', ancestor_ids=(120,)),
    ReportingCategory(
        name='Ministry and Worship', db_id=150,
        css_class='cat-ministry-and-worship',
        background='#DCE6F1', font='#000000', ancestor_ids=(150,)),
    ReportingCategory(
        name='Office & Administration', db_id=140,
        css_class='cat-office-and-administration',
        background='#4F81BD', font='#FFFFFF', ancestor_ids=(140,)),
    ReportingCategory(
        name='Food & Hospitality', db_id=130,
        css_class='cat-food-and-hospitality',
        background='#F4F199', font='#000000', ancestor_ids=(130,)),
    ReportingCategory(
        name='Gifts & Love Offerings', db_id=190,
        css_class='cat-gifts-and-love-offerings',
        background='#A9D18E', font='#000000', ancestor_ids=(190,)),
    # "Staff & Benefits" (240) split into Robert (RJ, 242) and Rosemary (RM, 243),
    # both "Priority Health" leaves under "Senior Pastors" (241). 240 still rolls
    # up to Robert, which misattributes Rosemary's spend — legacy, preserved.
    ReportingCategory(
        name='Robert Benefits and Medical', db_id=242,
        css_class='cat-robert-benefits-and-medical',
        background='#CCC0DA', font='#000000', ancestor_ids=(240, 242)),
    ReportingCategory(
        name='Rosemary Benefits & Medical', db_id=243,
        css_class='cat-rosemary-benefits-and-medical',
        background='#F4B6C2', font='#000000', ancestor_ids=(243,)),
    ReportingCategory(
        name='Travel & Vehicle', db_id=160, css_class='cat-travel-and-vehicle',
        background='#F4B683', font='#000000', ancestor_ids=(160,)),
    ReportingCategory(
        name='Insurance, Taxes & Fees', db_id=230,
        css_class='cat-insurance-taxes-and-fees',
        background='#FCD5B4', font='#000000',
        # 358 / 400 are municipal payees that report here.
        ancestor_ids=(230, 358, 400)),
    ReportingCategory(
        name='Housing', db_id=300, css_class='cat-housing',
        background='#DDD9C4', font='#000000',
        ancestor_ids=(300, 310, 320, 330, 340, 350, 2)),
    ReportingCategory(
        name='Personal', db_id=3, css_class='cat-personal',
        background='#948A54', font='#FFFFFF', ancestor_ids=(3,)),
    # A sentinel, not a row: picking it clears category_id, hence db_id=None.
    # 1 (Church) and 364 (Electronic Payment) both resolve here.
    ReportingCategory(
        name='Uncategorized', db_id=None, css_class='cat-uncategorized',
        background='#BFBFBF', font='#000000', ancestor_ids=(364, 1)),
)


def _check_no_bucket_shares_a_name_or_id() -> None:
    """Two buckets claiming one name or one id is a silent overwrite.

    As four dict literals this was invisible: a repeated key made the later
    entry win in three of them and the earlier one win in none, so the maps
    disagreed about a bucket that looked present in all four.
    """
    names = [c.name for c in REPORTING_CATEGORIES]
    if len(set(names)) != len(names):
        raise ValueError(f'duplicate reporting-category name in {names}')
    seen: dict[int, str] = {}
    for category in REPORTING_CATEGORIES:
        for ancestor in category.ancestor_ids:
            if ancestor in seen:
                raise ValueError(
                    f'category id {ancestor} rolls up to both {seen[ancestor]!r} '
                    f'and {category.name!r}')
            seen[ancestor] = category.name


_check_no_bucket_shares_a_name_or_id()


# ── The four derived views ────────────────────────────────────────────────────
# Plain dicts, not models: these are read with `.get()` / `in` by code that
# predates the taxonomy port, and they are what the golden test pins.

# name -> representative categories.id. "Uncategorized" clears category_id.
REPORTING_CATEGORY_DB_MAP: dict[str, int | None] = {
    c.name: c.db_id for c in REPORTING_CATEGORIES
}

# name -> the cat-* CSS class baked into report.html rows. report.html is a
# STATIC file: its row colour comes from this class, NOT from a live DB read, so
# a category change must rewrite this class on disk to survive a page refresh
# (the DB write alone is invisible to the static file).
REPORTING_CATEGORY_CLASS: dict[str, str] = {
    c.name: c.css_class for c in REPORTING_CATEGORIES
}

# name -> (background, font) hex. Colours the synthetic "Receipt Only" report
# rows; the static per-statement report.html files carry these as baked-in cat-*
# CSS instead.
REPORTING_CATEGORY_STYLE: dict[str, tuple[str, str]] = {
    c.name: (c.background, c.font) for c in REPORTING_CATEGORIES
}

# categories.id -> reporting bucket, walked up the ancestor chain. Read only
# with `.get()`, so the key order here is not part of the contract (unlike the
# three name-keyed views above, whose order is the dialog's display order).
REPORTING_CATEGORY_ANCESTOR_MAP: dict[int, str] = {
    ancestor: c.name
    for c in REPORTING_CATEGORIES
    for ancestor in c.ancestor_ids
}


def by_name(name: str) -> ReportingCategory | None:
    """The bucket a report/dialog label refers to, or None."""
    wanted = str(name or '').strip()
    return next((c for c in REPORTING_CATEGORIES if c.name == wanted), None)
