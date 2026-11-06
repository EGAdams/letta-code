"""Model configuration and readiness Strategy registry.

CLI presence and credential-file existence prove configuration only. Built-in
probes always leave available=False until an authenticated runtime check is
implemented. No credential contents are read and no model is called here.
Custom verified probes can be registered through VerifyProbe/register_probe.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

from paths import HERE

CONFIG_PATH = Path(HERE) / "config" / "model_registry.json"


@dataclass(frozen=True)
class ModelHealth:
    available: bool
    status: str  # "configured" | "unconfigured"
    detail: str
    checked_at: float


class ModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    label: str = ""
    task_capabilities: tuple[str, ...] = ()
    can_write: StrictBool = False
    cost_tier: str = "unknown"
    dispatch_strategy: str = "unavailable"
    verify_kind: str = "none"
    verify_arg: str = ""


class VerifyProbe(Protocol):
    def __call__(self, arg: str) -> ModelHealth: ...


def _verify_cli(arg: str) -> ModelHealth:
    """Configuration detected only if the named CLI binary is on PATH, locally. No
    invocation, no version check -- presence is the whole signal."""
    now = time.time()
    found = shutil.which(arg) if arg else None
    if found:
        return ModelHealth(False, "configured", f"'{arg}' CLI found; authentication and model execution unverified", now)
    return ModelHealth(False, "unconfigured", f"'{arg}' CLI not found on PATH", now)


def _verify_credentials(arg: str) -> ModelHealth:
    """Configuration detected only if the named credential file exists locally. The file
    is never opened/parsed here -- existence is the whole signal, so this
    probe cannot leak a token."""
    now = time.time()
    path = Path(os.path.expanduser(arg)) if arg else None
    try:
        exists = bool(path and path.is_file())
    except OSError:
        exists = False
    if exists:
        return ModelHealth(False, "configured", "credential file present; authentication and model execution unverified", now)
    return ModelHealth(False, "unconfigured", f"credential file missing: {path}", now)


def _verify_none(arg: str) -> ModelHealth:
    """No verification method exists for this entry; always unconfigured."""
    return ModelHealth(False, "unconfigured", arg or "no verification method is implemented", time.time())


VERIFY_PROBES: dict[str, VerifyProbe] = {
    "cli": _verify_cli,
    "credentials": _verify_credentials,
    "none": _verify_none,
}


def register_probe(kind: str, probe: VerifyProbe) -> None:
    """Plugin hook: add a new `verify_kind` without editing this module."""
    VERIFY_PROBES[kind] = probe


def load_entries(path: Path = CONFIG_PATH) -> list[ModelEntry]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    entries = []
    seen: set[str] = set()
    for item in raw:
        try:
            entry = ModelEntry.model_validate(item)
        except ValidationError:
            continue
        if entry.id in seen:
            continue
        seen.add(entry.id)
        entries.append(entry)
    return entries


def verify(entry: ModelEntry) -> ModelHealth:
    probe = VERIFY_PROBES.get(entry.verify_kind, _verify_none)
    try:
        return probe(entry.verify_arg)
    except OSError as exc:
        return ModelHealth(False, "unconfigured", f"verification failed: {exc}", time.time())


def registry(path: Path = CONFIG_PATH) -> list[dict]:
    """One row per validated model configuration, with explicit verification status."""
    out = []
    for entry in load_entries(path):
        health = verify(entry)
        out.append({
            "id": entry.id,
            "label": entry.label or entry.id,
            "task_capabilities": list(entry.task_capabilities),
            "can_write": entry.can_write,
            "cost_tier": entry.cost_tier,
            "dispatch_strategy": entry.dispatch_strategy,
            "available": health.available,
            "status": health.status,
            "configured": health.status == "configured",
            "verification": "runtime-verified" if health.available else "runtime-unverified",
            "detail": health.detail,
            "checked_at": health.checked_at,
        })
    return out


def provider_selection_payload(current: str = "", path: Path = CONFIG_PATH) -> dict:
    """The exact shape `renderWorkerProviderSelection`
    (js/abstract/worker-activity-render.js) already expects:
    `{current, providers: [{id, label, available}]}`."""
    entries = registry(path)
    return {
        "current": current,
        "providers": [
            {"id": e["id"], "label": e["label"], "available": e["available"],
             "configured": e.get("configured", False), "detail": e.get("detail", "")}
            for e in entries
        ],
    }
