"""Interface-backed, compare-and-swap undo for expense category changes."""

from __future__ import annotations

import json
import os
import secrets
import threading
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CategoryChange:
    expense_id: int
    previous_category_id: int | None
    category_id: int | None
    previous_reporting_category: str
    reporting_category: str
    date: str
    signed_amount: str
    vendor_key: str
    description: str
    report_path: str


class ICategoryUndoStore(ABC):
    @abstractmethod
    def record(self, action: CategoryChange) -> str:
        raise NotImplementedError

    @abstractmethod
    def get(self, token: str) -> CategoryChange | None:
        raise NotImplementedError

    @abstractmethod
    def is_used(self, token: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mark_used(self, token: str) -> None:
        raise NotImplementedError


class JsonCategoryUndoStore(ICategoryUndoStore):
    """Small persistent action journal; never stores financial document paths."""

    def __init__(self, path: str | Path, max_actions: int = 500):
        self._path = Path(path)
        self._max_actions = max_actions
        self._lock = threading.Lock()

    def _read(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"actions": {}}
        except (OSError, ValueError):
            return {"actions": {}}

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
        )
        os.replace(temporary, self._path)

    def record(self, action: CategoryChange) -> str:
        token = secrets.token_urlsafe(24)
        with self._lock:
            data = self._read()
            actions = data.setdefault("actions", {})
            actions[token] = {"used": False, "action": asdict(action)}
            while len(actions) > self._max_actions:
                actions.pop(next(iter(actions)))
            self._write(data)
        return token

    def get(self, token: str) -> CategoryChange | None:
        with self._lock:
            entry = self._read().get("actions", {}).get(token)
        if not isinstance(entry, dict) or not isinstance(entry.get("action"), dict):
            return None
        try:
            return CategoryChange(**entry["action"])
        except (TypeError, ValueError):
            return None

    def is_used(self, token: str) -> bool:
        with self._lock:
            entry = self._read().get("actions", {}).get(token)
        return bool(entry and entry.get("used"))

    def mark_used(self, token: str) -> None:
        with self._lock:
            data = self._read()
            entry = data.get("actions", {}).get(token)
            if entry:
                entry["used"] = True
                self._write(data)


class ICategoryRepository(ABC):
    @abstractmethod
    def restore_if_current(
        self,
        expense_id: int,
        expected_category_id: int | None,
        target_category_id: int | None,
    ) -> str:
        """Return restored, already_restored, conflict, or missing."""
        raise NotImplementedError


class MySqlCategoryRepository(ICategoryRepository):
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def restore_if_current(
        self,
        expense_id: int,
        expected_category_id: int | None,
        target_category_id: int | None,
    ) -> str:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE expenses SET category_id=%s "
                    "WHERE id=%s AND category_id <=> %s",
                    (target_category_id, expense_id, expected_category_id),
                )
                if cursor.rowcount == 1:
                    return "restored"
                cursor.execute(
                    "SELECT category_id FROM expenses WHERE id=%s", (expense_id,)
                )
                row = cursor.fetchone()
        if row is None:
            return "missing"
        return (
            "already_restored"
            if row.get("category_id") == target_category_id
            else "conflict"
        )


class CategoryUndoService:
    def __init__(
        self,
        store: ICategoryUndoStore,
        repository: ICategoryRepository,
    ):
        self._store = store
        self._repository = repository

    def record(self, action: CategoryChange) -> str | None:
        if action.previous_category_id == action.category_id:
            return None
        return self._store.record(action)

    def undo(self, token: str) -> dict:
        if not token:
            return {"status": "missing", "error": "Undo token is required."}
        action = self._store.get(token)
        if action is None:
            return {
                "status": "missing",
                "error": "That undo action was not found or has expired.",
            }
        if self._store.is_used(token):
            return {"status": "already_restored", "action": asdict(action)}
        status = self._repository.restore_if_current(
            action.expense_id,
            action.category_id,
            action.previous_category_id,
        )
        if status in {"restored", "already_restored"}:
            self._store.mark_used(token)
            return {"status": status, "action": asdict(action)}
        if status == "conflict":
            return {
                "status": status,
                "error": (
                    "Expense category changed again; refusing to overwrite it."
                ),
            }
        return {"status": "missing", "error": "The expense no longer exists."}
