from category_undo import (
    CategoryChange,
    CategoryUndoService,
    ICategoryRepository,
    ICategoryUndoStore,
)


class MemoryUndoStore(ICategoryUndoStore):
    def __init__(self):
        self.actions = {}
        self.used = set()

    def record(self, action):
        self.actions["token-1"] = action
        return "token-1"

    def get(self, token):
        return self.actions.get(token)

    def is_used(self, token):
        return token in self.used

    def mark_used(self, token):
        self.used.add(token)


class MemoryCategoryRepository(ICategoryRepository):
    def __init__(self, category_id):
        self.category_id = category_id

    def restore_if_current(self, expense_id, expected_category_id, target_category_id):
        if self.category_id == target_category_id:
            return "already_restored"
        if self.category_id != expected_category_id:
            return "conflict"
        self.category_id = target_category_id
        return "restored"


def _action():
    return CategoryChange(
        expense_id=477,
        previous_category_id=190,
        category_id=243,
        previous_reporting_category="Gifts & Love Offerings",
        reporting_category="Rosemary Benefits & Medical",
        date="2025-01-13",
        signed_amount="-25.00",
        vendor_key="right_to_life",
        description="Right to Life",
        report_path="",
    )


def test_category_undo_service_restores_only_expected_current_value():
    store = MemoryUndoStore()
    repo = MemoryCategoryRepository(category_id=243)
    service = CategoryUndoService(store, repo)
    token = service.record(_action())

    result = service.undo(token)

    assert result["status"] == "restored"
    assert repo.category_id == 190
    assert store.is_used(token) is True


def test_category_undo_service_refuses_to_overwrite_newer_change():
    store = MemoryUndoStore()
    repo = MemoryCategoryRepository(category_id=130)
    service = CategoryUndoService(store, repo)
    token = service.record(_action())

    result = service.undo(token)

    assert result["status"] == "conflict"
    assert repo.category_id == 130
    assert store.is_used(token) is False
