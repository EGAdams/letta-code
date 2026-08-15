"""The single source of truth for the expense-category tree.

Replaces four hand-maintained dicts that were copied into five files
(`server.py`, `create_spreadsheet.py`, `apply_reporting_category_colors.py`,
`hydrate_report_categories_from_db.py`, `static_shared_vendor_overrides.py`):
`REPORTING_CATEGORY_DB_MAP`, `REPORTING_CATEGORY_CLASS`,
`REPORTING_CATEGORY_STYLE` and `REPORTING_CATEGORY_ANCESTOR_MAP`.

Two ideas carry the whole design:

* A **report category** is a node flagged `is_report_category`. An expense
  stores the most specific leaf it can; the bucket it *reports* under is found
  by walking `parent_id` upward to the nearest flagged ancestor. That walk is
  why storing leaf 218 (Right to Life) still totals under 190 (Gifts & Love
  Offerings) in green — no duplicated facts on the expense row.
* A node may carry an explicit `report_category_id` pointer that short-circuits
  the walk. This exists because the legacy maps contain deliberate
  irregularities (358 City of Walker Treasury and 400 City Of Grand Rapids are
  children of `1 Church` but report as *Insurance, Taxes & Fees*). Modelling
  them honestly beats pretending the tree is regular.

This module must not import anything from the dashboard package: it is shared
with `receipt_parsing_tools/create_spreadsheet.py`, which runs under a
different interpreter (see the xlsxwriter note at server.py's ancestor map).
Its only dependency is a connection factory passed in by the caller.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import Callable, Iterable, Mapping, Sequence

UNCATEGORIZED_LABEL = "Uncategorized"
UNCATEGORIZED_STYLE = ("#BFBFBF", "#000000")
UNCATEGORIZED_CSS_CLASS = "cat-uncategorized"


@dataclass(frozen=True)
class CategoryNode:
    id: int
    parent_id: int | None
    name: str
    is_active: bool = True
    # Dialog/report presentation. Only meaningful on report categories.
    is_report_category: bool = False
    is_selectable: bool = False
    display_order: int = 0
    report_label: str | None = None
    report_bg: str | None = None
    report_fg: str | None = None
    css_class: str | None = None
    # Escape hatch for nodes whose bucket is not their nearest flagged ancestor.
    report_category_id: int | None = None
    # Accounting axes. Deliberately separate from the report bucket: a leaf can
    # report under "Insurance, Taxes & Fees" while classifying as Occupancy.
    irs_natural_class: str | None = None
    functional_class: str | None = None
    excluded_from_nonprofit_totals: bool = False
    # Attribution is per-expense, not per-vendor, under these nodes (e.g. the
    # unassigned senior-pastor medical bucket: one Walgreens row moving to
    # Rosemary must not repoint the `walgreens` vendor mapping).
    per_expense_only: bool = False

    @property
    def label(self) -> str:
        """What a report or the Set Category dialog shows for this node."""
        return self.report_label or self.name


@dataclass(frozen=True)
class ReportStyle:
    background: str
    font: str
    css_class: str


class ICategoryTaxonomy(ABC):
    """Read model over the category tree. Implementations must be immutable
    from the caller's point of view; refresh policy is an implementation
    detail."""

    @abstractmethod
    def all_nodes(self) -> Sequence[CategoryNode]:
        raise NotImplementedError

    @abstractmethod
    def get(self, category_id: int | None) -> CategoryNode | None:
        raise NotImplementedError

    @abstractmethod
    def report_category_for(self, category_id: int | None) -> CategoryNode | None:
        """The bucket `category_id` totals under, or None when uncategorized."""
        raise NotImplementedError

    @abstractmethod
    def selectable_report_categories(self) -> Sequence[CategoryNode]:
        """The Set Category dialog list, in display order."""
        raise NotImplementedError

    @abstractmethod
    def leaves_under(self, category_id: int) -> Sequence[CategoryNode]:
        raise NotImplementedError

    @abstractmethod
    def is_descendant(self, category_id: int, ancestor_id: int) -> bool:
        raise NotImplementedError

    # ── Derived helpers, identical for every implementation ──────────────
    def label_for(self, category_id: int | None) -> str:
        node = self.report_category_for(category_id)
        return node.label if node else UNCATEGORIZED_LABEL

    def style_for(self, category_id: int | None) -> ReportStyle:
        node = self.report_category_for(category_id)
        if node is None:
            return ReportStyle(*UNCATEGORIZED_STYLE, UNCATEGORIZED_CSS_CLASS)
        background, font = UNCATEGORIZED_STYLE
        return ReportStyle(
            node.report_bg or background,
            node.report_fg or font,
            node.css_class or UNCATEGORIZED_CSS_CLASS,
        )

    def css_class_for(self, category_id: int | None) -> str:
        return self.style_for(category_id).css_class

    def is_excluded_from_nonprofit_totals(self, category_id: int | None) -> bool:
        """True when this expense must be kept out of nonprofit totals until a
        human resolves it (the Personal / non-church case)."""
        for node in self._ancestry(category_id):
            if node.excluded_from_nonprofit_totals:
                return True
        return False

    def _ancestry(self, category_id: int | None) -> Iterable[CategoryNode]:
        seen: set[int] = set()
        current = category_id
        while current is not None and current not in seen:
            seen.add(current)
            node = self.get(current)
            if node is None:
                return
            yield node
            current = node.parent_id


class _IndexedTaxonomy(ICategoryTaxonomy):
    """Shared traversal over an in-memory node set. Both adapters reduce to
    this once they have their nodes; only the sourcing differs."""

    def __init__(self, nodes: Iterable[CategoryNode]):
        self._by_id: dict[int, CategoryNode] = {n.id: n for n in nodes}
        children: dict[int | None, list[CategoryNode]] = {}
        for node in self._by_id.values():
            children.setdefault(node.parent_id, []).append(node)
        self._children = children

    def all_nodes(self) -> Sequence[CategoryNode]:
        return tuple(self._by_id.values())

    def get(self, category_id: int | None) -> CategoryNode | None:
        if category_id is None:
            return None
        return self._by_id.get(int(category_id))

    def report_category_for(self, category_id: int | None) -> CategoryNode | None:
        seen: set[int] = set()
        current = category_id if category_id is None else int(category_id)
        while current is not None and current not in seen:
            seen.add(current)
            node = self._by_id.get(current)
            if node is None:
                return None
            # An explicit pointer wins over the walk, but never loops.
            if node.report_category_id is not None and node.report_category_id not in seen:
                current = node.report_category_id
                continue
            if node.is_report_category:
                return node
            current = node.parent_id
        return None

    def selectable_report_categories(self) -> Sequence[CategoryNode]:
        selectable = [
            n for n in self._by_id.values()
            if n.is_selectable and n.is_report_category and n.is_active
        ]
        selectable.sort(key=lambda n: (n.display_order, n.label))
        return tuple(selectable)

    def leaves_under(self, category_id: int) -> Sequence[CategoryNode]:
        out: list[CategoryNode] = []
        stack = list(self._children.get(int(category_id), ()))
        seen: set[int] = set()
        while stack:
            node = stack.pop()
            if node.id in seen:
                continue
            seen.add(node.id)
            kids = self._children.get(node.id, ())
            if kids:
                stack.extend(kids)
            else:
                out.append(node)
        out.sort(key=lambda n: n.id)
        return tuple(out)

    def is_descendant(self, category_id: int, ancestor_id: int) -> bool:
        if int(category_id) == int(ancestor_id):
            return True
        seen: set[int] = set()
        current: int | None = int(category_id)
        while current is not None and current not in seen:
            seen.add(current)
            node = self._by_id.get(current)
            if node is None:
                return False
            if node.parent_id == int(ancestor_id):
                return True
            current = node.parent_id
        return False


class StaticCategoryTaxonomy(_IndexedTaxonomy):
    """A frozen snapshot. Used as the test double and as the offline fallback
    when the database is unreachable — a DB outage degrades the dialog to the
    legacy behaviour instead of emptying it."""


class FallbackCategoryTaxonomy(ICategoryTaxonomy):
    """Answers from `primary`, deferring to `secondary` when it cannot.

    Resilience belongs here rather than inside the MySQL adapter, which stays a
    pure adapter. "Cannot answer" means the primary raised, or returned nothing
    for an id the secondary knows — which covers a DB outage, a category created
    since the cache filled, and (the case that bit us) a primary wired to a
    stubbed connection in a test, where silently returning "Uncategorized" for
    every id looked like a real answer.
    """

    def __init__(self, primary: ICategoryTaxonomy, secondary: ICategoryTaxonomy):
        self._primary = primary
        self._secondary = secondary

    def _try(self, method: str, *args):
        try:
            value = getattr(self._primary, method)(*args)
        except Exception:
            value = None
        if value:
            return value
        return getattr(self._secondary, method)(*args)

    def all_nodes(self) -> Sequence[CategoryNode]:
        return self._try("all_nodes")

    def get(self, category_id: int | None) -> CategoryNode | None:
        return self._try("get", category_id)

    def report_category_for(self, category_id: int | None) -> CategoryNode | None:
        return self._try("report_category_for", category_id)

    def selectable_report_categories(self) -> Sequence[CategoryNode]:
        return self._try("selectable_report_categories")

    def leaves_under(self, category_id: int) -> Sequence[CategoryNode]:
        return self._try("leaves_under", category_id)

    def is_descendant(self, category_id: int, ancestor_id: int) -> bool:
        try:
            if self._primary.is_descendant(category_id, ancestor_id):
                return True
        except Exception:
            pass
        return self._secondary.is_descendant(category_id, ancestor_id)

    def invalidate(self) -> None:
        invalidate = getattr(self._primary, "invalidate", None)
        if callable(invalidate):
            invalidate()


class MySqlCategoryTaxonomy(ICategoryTaxonomy):
    """Live view over `categories`, cached for `ttl_seconds`.

    A pure adapter: it either answers from the database or raises. Compose it
    with `FallbackCategoryTaxonomy` for resilience — see the composition root in
    server.py. Presentation columns are read only when present, so this can ship
    ahead of migration 001.
    """

    _PRESENTATION_COLUMNS = (
        "is_report_category", "is_selectable", "display_order", "report_label",
        "report_bg", "report_fg", "css_class", "report_category_id",
        "irs_natural_class", "functional_class",
        "excluded_from_nonprofit_totals", "per_expense_only",
    )

    def __init__(
        self,
        connection_factory: Callable[[], object],
        ttl_seconds: float = 60.0,
    ):
        self._connection_factory = connection_factory
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._snapshot: _IndexedTaxonomy | None = None
        self._loaded_at = 0.0

    def _available_columns(self, cursor) -> set[str]:
        cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'categories'"
        )
        return {
            str(row["COLUMN_NAME"] if isinstance(row, Mapping) else row[0])
            for row in cursor.fetchall()
        }

    def _load(self) -> _IndexedTaxonomy:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                present = self._available_columns(cursor)
                extra = [c for c in self._PRESENTATION_COLUMNS if c in present]
                columns = ["id", "parent_id", "name", "is_active", *extra]
                cursor.execute(
                    f"SELECT {', '.join(columns)} FROM categories"  # noqa: S608
                )
                rows = cursor.fetchall()

        nodes: list[CategoryNode] = []
        for row in rows:
            node = CategoryNode(
                id=int(row["id"]),
                parent_id=(
                    int(row["parent_id"]) if row.get("parent_id") is not None else None
                ),
                name=str(row["name"]),
                is_active=bool(row.get("is_active", 1)),
            )
            node = replace(
                node,
                is_report_category=bool(row.get("is_report_category", 0)),
                is_selectable=bool(row.get("is_selectable", 0)),
                display_order=int(row.get("display_order") or 0),
                report_label=row.get("report_label") or None,
                report_bg=row.get("report_bg") or None,
                report_fg=row.get("report_fg") or None,
                css_class=row.get("css_class") or None,
                report_category_id=(
                    int(row["report_category_id"])
                    if row.get("report_category_id") is not None
                    else None
                ),
                irs_natural_class=row.get("irs_natural_class") or None,
                functional_class=row.get("functional_class") or None,
                excluded_from_nonprofit_totals=bool(
                    row.get("excluded_from_nonprofit_totals", 0)),
                per_expense_only=bool(row.get("per_expense_only", 0)),
            )
            nodes.append(node)

        return _IndexedTaxonomy(nodes)

    def _current(self) -> ICategoryTaxonomy:
        with self._lock:
            fresh = (
                self._snapshot is not None
                and (time.monotonic() - self._loaded_at) < self._ttl_seconds
            )
            if fresh:
                return self._snapshot
        try:
            snapshot = self._load()
        except Exception:
            # Serve the last good snapshot through a blip; otherwise raise and
            # let FallbackCategoryTaxonomy decide.
            with self._lock:
                if self._snapshot is not None:
                    return self._snapshot
            raise
        with self._lock:
            self._snapshot = snapshot
            self._loaded_at = time.monotonic()
        return snapshot

    def invalidate(self) -> None:
        """Drop the cache so the next read reflects a just-applied change."""
        with self._lock:
            self._snapshot = None
            self._loaded_at = 0.0

    def all_nodes(self) -> Sequence[CategoryNode]:
        return self._current().all_nodes()

    def get(self, category_id: int | None) -> CategoryNode | None:
        return self._current().get(category_id)

    def report_category_for(self, category_id: int | None) -> CategoryNode | None:
        return self._current().report_category_for(category_id)

    def selectable_report_categories(self) -> Sequence[CategoryNode]:
        return self._current().selectable_report_categories()

    def leaves_under(self, category_id: int) -> Sequence[CategoryNode]:
        return self._current().leaves_under(category_id)

    def is_descendant(self, category_id: int, ancestor_id: int) -> bool:
        return self._current().is_descendant(category_id, ancestor_id)
