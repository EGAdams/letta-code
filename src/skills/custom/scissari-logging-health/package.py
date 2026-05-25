#!/usr/bin/env python3
"""
One-shot packager for scissari-logging-health.skill
Run from anywhere:  python3 /home/adamsl/letta-code/src/skills/custom/scissari-logging-health/package.py
Output:             /home/adamsl/letta-code/src/skills/custom/scissari-logging-health/scissari-logging-health.skill
"""

import zipfile
import fnmatch
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
SKILL_NAME = SKILL_DIR.name  # scissari-logging-health
OUTPUT_FILE = SKILL_DIR / f"{SKILL_NAME}.skill"

EXCLUDE_DIRS = {"__pycache__", "node_modules", "evals"}
EXCLUDE_GLOBS = {"*.pyc", "*.skill"}
EXCLUDE_FILES = {".DS_Store", "package.py"}


def should_exclude(rel_path: Path) -> bool:
    parts = rel_path.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    name = rel_path.name
    if name in EXCLUDE_FILES:
        return True
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_GLOBS)


def main():
    print(f"Packaging: {SKILL_DIR}")
    print(f"Output:    {OUTPUT_FILE}\n")

    with zipfile.ZipFile(OUTPUT_FILE, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(SKILL_DIR.rglob("*")):
            if not file_path.is_file():
                continue
            arcname = file_path.relative_to(SKILL_DIR.parent)
            if should_exclude(arcname):
                print(f"  Skipped: {arcname}")
                continue
            zf.write(file_path, arcname)
            print(f"  Added:   {arcname}")

    size_kb = OUTPUT_FILE.stat().st_size / 1024
    print(f"\nDone — {OUTPUT_FILE.name} ({size_kb:.1f} KB)")
    print("\nTo install in Cowork:")
    print("  1. Open Cowork settings → Plugins / Skills")
    print("  2. Choose 'Install from file'")
    print(f"  3. Select:  {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
