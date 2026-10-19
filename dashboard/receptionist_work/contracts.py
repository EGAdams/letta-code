"""Shared, runtime-validated JSON contracts from the canonical finance ADW."""
import os
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from finance.expense_fields import ExpenseFieldRules

FINANCE_ROOT = Path(os.getenv('ROL_FINANCE_ROOT', str(Path.home() / 'rol_finances'))).resolve()
for directory in (FINANCE_ROOT / 'adws',):
    if str(directory) not in sys.path:
        sys.path.append(str(directory))

from adw_modules.receptionist.models import BrowserCommand, WorkRequest, WorkResult, WorkState


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    command_id: str = Field(min_length=8, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    client_id: str = Field(min_length=8, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')


class StoredEditIntent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    command: BrowserCommand
    status: str
    receipt: dict | None = None


class TrainingEditRequest(ExpenseFieldRules):
    operation_id: str = Field(min_length=8, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    expense_id: int = Field(gt=0)
    category_name: str
    distance_miles: float | None
    map_link: str
