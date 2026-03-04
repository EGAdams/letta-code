#!/usr/bin/env python3
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Iterable

DEFAULT_ROOTS = [
    Path("/tmp"),
    Path("/home/adamsl/rol_finances/readable_documents/reports"),
]
ALLOWED_EXTS = {".log", ".txt"}
KEYWORDS = ("executor", "mcp")
MAX_DEPTH = 4
MAX_RESULTS = 10


def iter_files(root: Path, max_depth: int) -> Iterable[Path]:
    if not root.exists():
        return
    base_depth = len(root.resolve().parts)
    for dirpath, dirnames, filenames in os.walk(root):
        current_depth = len(Path(dirpath).resolve().parts) - base_depth
        if current_depth >= max_depth:
            dirnames[:] = []
        for filename in filenames:
            yield Path(dirpath) / filename


def is_candidate(path: Path) -> bool:
    name = path.name.lower()
    if not any(k in name for k in KEYWORDS):
        return False
    if path.suffix.lower() not in ALLOWED_EXTS:
        return False
    return True


def main() -> None:
    candidates = []
    for root in DEFAULT_ROOTS:
        for path in iter_files(root, MAX_DEPTH):
            if is_candidate(path):
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                candidates.append((mtime, path))

    if not candidates:
        print("No executor logs found")
        return

    candidates.sort(key=lambda item: item[0], reverse=True)
    for mtime, path in candidates[:MAX_RESULTS]:
        stamp = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{stamp}  {path}")


if __name__ == "__main__":
    main()
