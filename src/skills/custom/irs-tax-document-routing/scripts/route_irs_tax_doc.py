#!/usr/bin/env python3
"""Build a normalized IRS tax routing payload."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_for(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create IRS tax document routing payload")
    parser.add_argument("file_path", help="Path to scanned IRS/tax file")
    parser.add_argument("--routing-key", default="tax.irs_generic")
    parser.add_argument("--confidence", type=float, default=0.0)
    parser.add_argument("--reason", action="append", default=[])
    args = parser.parse_args()

    path = Path(args.file_path).expanduser()
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    payload = {
        "file_path": str(path),
        "filename": path.name,
        "sha256": sha256_for(path),
        "routing_key": args.routing_key,
        "confidence": args.confidence,
        "reasons": args.reason,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
