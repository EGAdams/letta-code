"""The only module that selects concrete work, storage and editor adapters."""
import os
from pathlib import Path

from .contracts import FINANCE_ROOT
from .application import ReceptionistWorkApplication
from .adw_runner import FinanceAdwRunner, FinanceExpenseEditCommand
from .training_editor import TrainingExpenseEditor
from .intent_store import SqliteEditIntents

_work = None
_editor = None


def save_command():
    return FinanceExpenseEditCommand(FinanceAdwRunner(FINANCE_ROOT, 'http://127.0.0.1:8765'))


def work_application():
    global _work
    if _work is None:
        from adw_modules.receptionist.store import SqliteWorkStore
        from adw_modules.receptionist.training import ROOT
        _work = ReceptionistWorkApplication(
            FinanceAdwRunner(FINANCE_ROOT, os.getenv('RECEPTIONIST_DASHBOARD_URL', 'http://127.0.0.1:8765')),
            SqliteWorkStore(ROOT / 'work.sqlite'))
    return _work


def training_editor():
    global _editor
    if _editor is None:
        from adw_modules.receptionist.store import SqliteWorkStore
        from adw_modules.receptionist.training import ROOT, connection
        from adw_modules.tax_work.database import MySqlCategories
        from category_taxonomy import CategoryNode, StaticCategoryTaxonomy
        from finance.category_naming import TaxonomyCategoryNamer
        from finance.expense_categories import ExpenseCategoryCatalog
        from finance.expense_edit_repository import MySqlExpenseRecordRepository
        from finance.expense_edit_audit import AuditedExpenseEditCommand, CallableExpenseEditCommand, JsonlExpenseEditAuditLog
        from finance.expense_edit_service import Collaborators, edit_stored_expense
        categories = MySqlCategories(connection).snapshot().categories
        taxonomy = StaticCategoryTaxonomy([CategoryNode(id=c.id, parent_id=c.parent_id, name=c.name) for c in categories])
        catalog = ExpenseCategoryCatalog(lambda: taxonomy, TaxonomyCategoryNamer(taxonomy.label_for, lambda _: (None, None)))
        repo = MySqlExpenseRecordRepository(connection, catalog)

        class TrainingReportSynchronizer:
            def synchronize(self, before, after):
                return None  # Synthetic fixture has no statement reports to synchronize.

        deps = Collaborators(get_expense_edit_repository=lambda: repo,
                             taxonomy_category_namer=lambda: catalog,
                             invalidate_receipt_index=lambda: None,
                             synchronize_recent_report_image=lambda *a, **k: {},
                             vendor_prefix=lambda _: 'training',
                             static_expense_report_synchronizer=lambda _: TrainingReportSynchronizer(),
                             rol_finances_reports_parent=str(ROOT))
        command = AuditedExpenseEditCommand(
            CallableExpenseEditCommand(lambda data: edit_stored_expense(deps, data, namer=catalog)),
            JsonlExpenseEditAuditLog(str(ROOT / 'expense-edit-audit.jsonl')))
        SqliteWorkStore(ROOT / 'work.sqlite')
        _editor = TrainingExpenseEditor(repo, catalog, command, SqliteEditIntents(ROOT / 'work.sqlite'))
    return _editor


def document_path(requested: str) -> Path:
    from adw_modules.receptionist.training import ROOT
    base = (ROOT / 'readable_documents').resolve()
    candidate = (ROOT / requested).resolve()
    if not candidate.is_relative_to(base) or not candidate.is_file():
        raise ValueError('The training document was not found.')
    return candidate
