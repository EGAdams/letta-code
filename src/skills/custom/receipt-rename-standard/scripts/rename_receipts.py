#!/usr/bin/env python3
"""Rename receipt files to <vendor>_MM_DD_YY_<dollars>_<cents>.<ext>.

Uses parse_and_categorize.py (local engine) to extract transaction_date and total
when they are missing from the filename.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_ROOT = Path("/home/adamsl/rol_finances/readable_documents/receipts")
PARSER = Path(
    "/home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/receipt_parsing_tools/parse_and_categorize.py"
)

EXTS = {".png", ".jpg", ".jpeg", ".pdf", ".tif", ".tiff"}
STD_RE = re.compile(
    r"^(?P<vendor>[a-z0-9_]+)_(?P<mm>\d{2})_(?P<dd>\d{2})_(?P<yy>\d{2})_(?P<dollars>\d+)_(?P<cents>\d{2})$",
    re.I,
)


@dataclass
class Result:
    old_path: str
    new_path: str
    status: str
    vendor: str = ""
    date: str = ""
    total: str = ""
    reason: str = ""


def slugify(text: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "receipt"


def normalize_stem(stem: str) -> str:
    # collapse double underscores, remove trailing extra extensions
    stem = re.sub(r"__+", "_", stem)
    return stem


def parse_filename(stem: str):
    stem = normalize_stem(stem)
    m = STD_RE.match(stem)
    if not m:
        return None


def _extract_date_from_raw_text(raw_text: str) -> str | None:
    # Look for mm/dd/yy patterns; prefer ones with a nearby time (AM/PM)
    candidates = []
    for line in raw_text.splitlines():
        m = re.search(r"(\d{2}/\d{2}/\d{2})", line)
        if not m:
            continue
        date_str = m.group(1)
        score = 1
        if re.search(r"\b\d{1,2}:\d{2}\s*(AM|PM)\b", line, re.I):
            score += 2
        if re.search(r"\bTOTAL\b|AMOUNT\s+DUE", line, re.I):
            score += 1
        candidates.append((score, date_str))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]
    return m.groupdict()


def _extract_total_from_raw_text(raw_text: str) -> str | None:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    candidates = []
    for line in lines:
        if re.search(r"\bTOTAL\b", line, re.I) and not re.search(r"\b(TAX|SUB|SAV)\b", line, re.I):
            amounts = re.findall(r"\b\d+\.\d{2}\b", line)
            for amt in amounts:
                candidates.append(amt)
    if candidates:
        return max(candidates, key=lambda x: float(x))

    # Fallback: use the largest amount in the last 10 lines (often total is near footer)
    tail = "\n".join(lines[-10:])
    amounts = re.findall(r"\b\d+\.\d{2}\b", tail)
    if amounts:
        return max(amounts, key=lambda x: float(x))
    return None


def parse_receipt(path: Path) -> tuple[str | None, str | None, str | None]:
    """Return (merchant, date_str, total_str)"""
    cmd = ["python3", str(PARSER), "--file", str(path), "--engine", "local", "--json", "--no-pick"]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        return None, None, None
    try:
        payload = json.loads(result.stdout)
    except Exception:
        return None, None, None

    party = payload.get("party") if isinstance(payload, dict) else None
    merchant = (party.get("merchant_name") if isinstance(party, dict) else None) or payload.get("merchant_name") or payload.get("merchant")

    date_str = payload.get("transaction_date") or payload.get("date")
    totals = payload.get("totals") if isinstance(payload, dict) else None
    total = None
    if isinstance(totals, dict):
        total = totals.get("total") or totals.get("amount") or totals.get("grand_total")
    if total is None:
        total = payload.get("total") or payload.get("amount")

    raw_text = payload.get("meta", {}).get("raw_text") or payload.get("raw_text")
    if isinstance(raw_text, list):
        raw_text = "\n".join(raw_text)
    raw_text = str(raw_text or "")
    raw_total = _extract_total_from_raw_text(raw_text) if raw_text else None
    raw_date = _extract_date_from_raw_text(raw_text) if raw_text else None

    # Prefer raw_total when parsed total is missing or clearly too small
    if raw_total:
        try:
            total_val = float(total) if total is not None else None
            raw_val = float(raw_total)
        except Exception:
            total_val = None
            raw_val = None
        if total_val is None or (raw_val is not None and total_val < raw_val / 2):
            total = raw_total

    if raw_date and (not date_str or str(date_str).startswith(str(datetime.now().date()))):
        date_str = raw_date

    return (merchant or None, str(date_str) if date_str else None, str(total) if total is not None else None)


def format_date(date_str: str) -> tuple[str | None, str | None, str | None]:
    """Return (mm, dd, yy) or (None, None, None). Accept YYYY-MM-DD or MM/DD/YY"""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%m"), dt.strftime("%d"), dt.strftime("%y")
        except Exception:
            continue
    return None, None, None


def format_amount(amount_str: str) -> tuple[str | None, str | None]:
    try:
        amt = float(str(amount_str).replace("$", "").replace(",", ""))
    except Exception:
        return None, None
    dollars = int(amt)
    cents = int(round((amt - dollars) * 100))
    return str(dollars), f"{cents:02d}"


def build_new_stem(vendor: str, mm: str, dd: str, yy: str, dollars: str, cents: str) -> str:
    return f"{vendor}_{mm}_{dd}_{yy}_{dollars}_{cents}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rename receipt files to standard format")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--execute", action="store_true", help="Perform renames (otherwise dry-run)")
    parser.add_argument("--report-dir", type=Path, default=Path("/home/adamsl/rol_finances/reports"))
    args = parser.parse_args()

    root = args.root
    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    results: list[Result] = []
    files = [p for p in root.rglob("*") if p.suffix.lower() in EXTS]

    for path in files:
        stem = normalize_stem(path.stem)
        ext = path.suffix.lower()
        parsed = parse_filename(stem)

        if parsed:
            vendor = slugify(parsed["vendor"])
            new_stem = build_new_stem(
                vendor,
                parsed["mm"],
                parsed["dd"],
                parsed["yy"],
                parsed["dollars"],
                parsed["cents"],
            )
            new_path = path.with_name(new_stem + ext)
            if new_path == path:
                results.append(Result(str(path), str(new_path), "ok", vendor=vendor))
            elif new_path.exists():
                results.append(Result(str(path), str(new_path), "skip", reason="target exists"))
            else:
                if args.execute:
                    path.rename(new_path)
                    results.append(Result(str(path), str(new_path), "renamed"))
                else:
                    results.append(Result(str(path), str(new_path), "dry-run"))
            continue
        else:
            merchant, date_str, total_str = parse_receipt(path)
            if not (date_str and total_str):
                results.append(Result(str(path), "", "skip", reason="missing date/total"))
                continue
            mm, dd, yy = format_date(date_str)
            dollars, cents = format_amount(total_str)
            if not (mm and dd and yy and dollars and cents):
                results.append(Result(str(path), "", "skip", reason="unparseable date/total"))
                continue
            vendor = slugify(path.stem.split("_")[0])
            if vendor in ("receipt", "scan", "image") and merchant:
                vendor = slugify(merchant)
            new_stem = build_new_stem(vendor, mm, dd, yy, dollars, cents)

        new_path = path.with_name(new_stem + ext)
        if new_path == path:
            results.append(Result(str(path), str(new_path), "ok", vendor=new_stem.split("_")[0]))
            continue
        if new_path.exists():
            results.append(Result(str(path), str(new_path), "skip", reason="target exists"))
            continue

        if args.execute:
            path.rename(new_path)
            results.append(Result(str(path), str(new_path), "renamed"))
        else:
            results.append(Result(str(path), str(new_path), "dry-run"))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = report_dir / f"receipt_rename_report_{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["old_path", "new_path", "status", "reason"])
        for r in results:
            writer.writerow([r.old_path, r.new_path, r.status, r.reason])

    print(csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())