#!/usr/bin/env python3
"""Fix id_light mismatches from integrity HTML report."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, date
from html import unescape
from pathlib import Path
import os
import re
import sys

from dotenv import load_dotenv
import pymysql

ROL_ROOT = Path("/home/adamsl/rol_finances")
ENV_PATH = Path("/home/adamsl/planner/.env")
REPORT_DIR = Path("/home/adamsl/rol_finances/reports")

sys.path.insert(0, str(ROL_ROOT))
from tools.generate_id_light.GenerateIDLight import GenerateIDLight  # noqa: E402
from tools.create_id_light.CreateIDLite import CreateIDLite  # noqa: E402
from parsing_router.gemini_cli import run_gemini_prompt  # noqa: E402


@dataclass
class MismatchRow:
    row_id: int
    id_light: str
    expected_id_light: str
    expense_date: str | None
    amount: str | None
    description: str | None
    reason: str


def connect_db():
    load_dotenv(ENV_PATH)
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("NON_PROFIT_USER"),
        password=os.getenv("NON_PROFIT_PASSWORD", ""),
        database=os.getenv("NON_PROFIT_DB_NAME", "nonprofit_finance"),
        port=int(os.getenv("DB_PORT", "3306")),
    )


def strip_tags(text: str) -> str:
    return unescape(re.sub(r"<.*?>", "", text, flags=re.S)).strip()


def parse_invalid_rows(report_path: Path) -> tuple[list[str], list[list[str]]]:
    html = report_path.read_text(encoding="utf-8")
    marker = "Invalid id_light Rows"
    start = html.find(marker)
    if start == -1:
        raise SystemExit("Could not find 'Invalid id_light Rows' section.")
    table_start = html.find("<table", start)
    table_end = html.find("</table>", table_start)
    if table_start == -1 or table_end == -1:
        raise SystemExit("Could not find invalid rows table.")
    section = html[table_start:table_end]
    rows = re.findall(r"<tr>(.*?)</tr>", section, flags=re.S)
    if not rows:
        return [], []

    header_cells = re.findall(r"<t[hd]>(.*?)</t[hd]>", rows[0], flags=re.S)
    headers = [strip_tags(c) for c in header_cells]

    data_rows: list[list[str]] = []
    for row in rows[1:]:
        cells = [strip_tags(c) for c in re.findall(r"<t[hd]>(.*?)</t[hd]>", row, flags=re.S)]
        if cells:
            data_rows.append(cells)
    return headers, data_rows


def parse_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except Exception:
        return None


def parse_float(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text)
    except Exception:
        return None


def slugify_vendor_key(text: str) -> str:
    lowered = (text or "").lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return cleaned


def extract_vendor_hints(description: str | None) -> list[str]:
    if not description:
        return []
    text = re.sub(r"\s+FROM\s+CARD:.*$", "", description, flags=re.IGNORECASE).strip()
    hints: list[str] = []
    if " - " in text:
        left, right = text.split(" - ", 1)
        if left.strip():
            hints.append(left.strip())
        to_match = re.search(r"\bTO\s+(.+)$", right, flags=re.IGNORECASE)
        if to_match and to_match.group(1).strip():
            hints.append(to_match.group(1).strip())
    return hints


def normalize_vendor_base(base: str) -> str:
    value = base
    pattern = re.compile(
        r"^(?P<head>.+?)_(\d{2})_(\d{2})_(\d{2}|\d{4})_(\d+)_([0-9]{2})$"
    )
    while True:
        match = pattern.match(value)
        if not match:
            break
        value = match.group("head")
    return value


def build_yaml_regex(description: str) -> str:
    tokens = [t for t in re.split(r"\s+", (description or "").strip()) if t]
    escaped = [re.escape(token) for token in tokens]
    return "^" + r"\s+".join(escaped) + "$"


def append_yaml_pattern(
    yaml_path: Path,
    manual_id_light: str,
    description: str,
) -> bool:
    regex = build_yaml_regex(description)
    regex_yaml = regex.replace("\\", "\\\\")
    vendor_base = normalize_vendor_base(manual_id_light)
    name = vendor_base
    base = vendor_base
    block = (
        f"\n  - name: {name}\n"
        f"    base: {base}\n"
        f"    regex: \"{regex_yaml}\"\n"
        f"    flags: [ IGNORECASE ]\n"
    )
    text = yaml_path.read_text(encoding="utf-8")
    if regex_yaml in text:
        return False
    yaml_path.write_text(text.rstrip() + block, encoding="utf-8")
    return True


def match_yaml_base(patterns, description: str | None) -> str | None:
    if not description:
        return None
    for pattern in patterns:
        regex_obj = pattern.get("regex")
        if regex_obj and regex_obj.search(description):
            return normalize_vendor_base(pattern.get("base") or "")
    return None


def extract_description_date(description: str | None) -> str | None:
    if not description:
        return None
    match = re.search(r"\bON\s+(\d{6})\b", description, flags=re.IGNORECASE)
    if match:
        token = match.group(1)
        mm, dd, yy = token[:2], token[2:4], token[4:6]
        try:
            year = 2000 + int(yy)
            return f"{year:04d}-{int(mm):02d}-{int(dd):02d}"
        except Exception:
            return None

    match = re.search(r"\b(\d{2})(\d{2})(\d{2})\b", description)
    if not match:
        return None
    mm, dd, yy = match.groups()
    try:
        year = 2000 + int(yy)
        return f"{year:04d}-{int(mm):02d}-{int(dd):02d}"
    except Exception:
        return None


def build_mismatch_rows(
    headers: list[str],
    rows: list[list[str]],
    include_missing: bool = False,
) -> list[MismatchRow]:
    if not headers:
        return []
    index = {name: idx for idx, name in enumerate(headers)}
    required = ["id", "id_light", "expected_id_light", "reason"]
    for name in required:
        if name not in index:
            raise SystemExit(f"Missing column: {name}")

    mismatches: list[MismatchRow] = []
    for row in rows:
        if len(row) <= index["reason"]:
            continue
        reason_value = row[index["reason"]]
        if reason_value == "missing_id_light":
            if not include_missing:
                continue
        elif reason_value != "mismatch":
            continue
        try:
            row_id = int(row[index["id"]])
        except Exception:
            continue
        mismatches.append(
            MismatchRow(
                row_id=row_id,
                id_light=row[index["id_light"]] if len(row) > index["id_light"] else "",
                expected_id_light=row[index["expected_id_light"]]
                if len(row) > index["expected_id_light"]
                else "",
                expense_date=row[index.get("expense_date", -1)]
                if "expense_date" in index and len(row) > index["expense_date"]
                else None,
                amount=row[index.get("amount", -1)]
                if "amount" in index and len(row) > index["amount"]
                else None,
                description=row[index.get("description", -1)]
                if "description" in index and len(row) > index["description"]
                else None,
                reason=reason_value,
            )
        )
    return mismatches


def prompt_choice(options: list[tuple[str, str]]) -> str:
    for idx, (value, source) in enumerate(options, start=1):
        print(f"  {idx}. {value} [{source}]")
    print("  l. llm opinion")
    choice = input("Choose option: ").strip().lower()
    if choice == "l":
        return "llm"
    try:
        index = int(choice) - 1
        if 0 <= index < len(options):
            return options[index][0]
    except Exception:
        pass
    return "skip"


def build_id_light_from_vendor(vendor_key: str, exp_date: date, amount: float) -> str:
    date_str = exp_date.strftime("%m/%d/%y")   # 2-digit year to match CreateIDLite
    return f"{vendor_key}_{date_str.replace('/', '_')}_{amount:.2f}".replace(".", "_")


def guess_vendor_key_with_gemini(description: str, date_text: str | None, amount_text: str | None, yaml_bases: list[str]) -> str | None:
    if not description:
        return None
    prompt = (
        "Return ONLY the vendor key (lowercase, underscores).\n"
        "Do NOT include date or amount; those are appended later.\n"
        "If description has 'Vendor - ...', use the vendor before the hyphen.\n"
        "If description has 'GIFT TO <vendor>', use the vendor after 'TO'.\n"
        "Examples: winn_dixie_2139_950x, wal_mart_46_950x.\n"
        f"Description: {description}\n"
        f"Date: {date_text or 'unknown'}\n"
        f"Amount: {amount_text or 'unknown'}\n"
        f"Known vendor keys: {', '.join(yaml_bases[:200])}\n"
        "Vendor key rules: lowercase, underscores, no extra text."
    )
    try:
        response = run_gemini_prompt(
            prompt,
            model_candidates=["gemini-2.5-flash-lite", "gemini-2.5-flash"],
        )
    except Exception as exc:
        print(f"[LLM] Gemini error: {exc}")
        return None
    if not response:
        return None
    return normalize_vendor_base(slugify_vendor_key(response.strip().splitlines()[0]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix id_light mismatches from integrity report.")
    parser.add_argument("--report", required=True, help="Path to id_light integrity HTML report")
    parser.add_argument(
        "--include-missing",
        action="store_true",
        help="Include missing_id_light rows (default: mismatches only)",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Process only missing_id_light rows (skip mismatches)",
    )
    parser.add_argument("--apply", action="store_true", help="Apply updates (still asks for confirmation)")
    parser.add_argument(
        "--auto-accept-yaml",
        action="store_true",
        help="Auto-accept YAML candidate without prompting when available",
    )
    parser.add_argument(
        "--auto-accept-vendor",
        action="store_true",
        help="Auto-accept vendor-prefix candidate when available",
    )
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        raise SystemExit(f"Report not found: {report_path}")

    headers, rows = parse_invalid_rows(report_path)
    include_missing = args.include_missing or args.only_missing
    mismatches = build_mismatch_rows(headers, rows, include_missing=include_missing)
    if args.only_missing:
        mismatches = [item for item in mismatches if item.reason == "missing_id_light"]

    generator = GenerateIDLight()
    creator = CreateIDLite()
    yaml_bases = [p.get("base") for p in creator._load_patterns() if p.get("base")]
    yaml_path = Path(creator.pattern_path)
    conn = connect_db()
    preview_lines = []
    conflict_rows = []
    updated = 0
    skipped_conflict = 0
    skipped_declined = 0
    recompute_warnings = 0
    remaining_missing = sum(1 for item in mismatches if item.reason == "missing_id_light")

    try:
        with conn.cursor() as cur:
            for item in mismatches:
                exp_date = parse_date(item.expense_date)
                amount = parse_float(item.amount)
                if not exp_date or amount is None:
                    preview_lines.append(f"SKIP missing date/amount for id={item.row_id}")
                    continue

                expected = item.expected_id_light
                if not expected:
                    if item.description:
                        try:
                            expected = generator.create_id_light(
                                item.description, exp_date, amount
                            )
                        except Exception:
                            expected = None
                if not expected:
                    preview_lines.append(f"SKIP missing expected_id_light for id={item.row_id}")
                    continue

                # YAML-based candidate
                yaml_candidate = None
                yaml_base = match_yaml_base(creator._load_patterns(), item.description)
                if yaml_base:
                    yaml_candidate = build_id_light_from_vendor(yaml_base, exp_date, amount)

                # Recompute via GenerateIDLight for warning only
                recomputed = None
                if item.description:
                    try:
                        recomputed = generator.create_id_light(item.description, exp_date, amount)
                    except Exception:
                        recomputed = None
                if recomputed and recomputed != expected:
                    recompute_warnings += 1
                    preview_lines.append(
                        f"WARN recompute differs id={item.row_id} report={expected} recompute={recomputed}"
                    )

                candidates: list[tuple[str, str]] = []
                if yaml_candidate:
                    candidates.append((yaml_candidate, "id_light.yaml"))
                for hint in extract_vendor_hints(item.description):
                    base = normalize_vendor_base(slugify_vendor_key(hint))
                    if base:
                        hint_candidate = build_id_light_from_vendor(base, exp_date, amount)
                        if hint_candidate not in [c[0] for c in candidates]:
                            candidates.append((hint_candidate, "vendor-prefix"))
                if expected and expected not in [c[0] for c in candidates]:
                    candidates.append((expected, "report"))

                if item.reason == "missing_id_light":
                    candidates.sort(
                        key=lambda entry: 0 if entry[1] == "report" else 1
                    )

                if not args.apply:
                    preview_lines.append(
                        f"DRYRUN id={item.row_id} old={item.id_light} candidates={candidates}"
                    )
                    continue

                non_interactive = not sys.stdin.isatty()
                if non_interactive and not (args.auto_accept_yaml or args.auto_accept_vendor):
                    preview_lines.append(f"SKIP no-tty id={item.row_id}")
                    continue

                if item.reason == "missing_id_light":
                    print(f"Missing remaining: {remaining_missing}")
                    remaining_missing = max(remaining_missing - 1, 0)
                print(f"Row {item.row_id}")
                print(f"Description: {item.description}")
                print(f"Amount: {item.amount}")
                desc_date = extract_description_date(item.description)
                if desc_date:
                    print(f"Description date: {desc_date}")
                print(f"Expense date: {item.expense_date}")
                choice = None
                selected_source = None
                if args.auto_accept_yaml and yaml_candidate:
                    choice = yaml_candidate
                    selected_source = "id_light.yaml"
                    print(f"Auto-accepted YAML id_light: {choice} [id_light.yaml]")
                if choice is None and args.auto_accept_vendor:
                    vendor_option = next(
                        (val for val, src in candidates if src == "vendor-prefix"), None
                    )
                    if vendor_option:
                        choice = vendor_option
                        selected_source = "vendor-prefix"
                        print(
                            f"Auto-accepted vendor id_light: {choice} [vendor-prefix]"
                        )
                if choice is None and non_interactive:
                    choice = expected
                    selected_source = "report"
                    preview_lines.append(
                        f"AUTO_ACCEPT report id={item.row_id}"
                    )
                if choice is None and len(candidates) >= 2:
                    print("Choose id_light candidate:")
                    choice = prompt_choice(candidates)
                    if choice not in {"skip", "llm"}:
                        selected_source = next(
                            (src for val, src in candidates if val == choice), None
                        )
                if choice is None:
                    choice = candidates[0][0]
                    selected_source = candidates[0][1]
                    print(f"Proposed id_light: {choice} [{candidates[0][1]}]")
                    confirm = input("Use this? (y/n): ").strip().lower()
                    if confirm != "y":
                        choice = "llm"

                if choice == "llm":
                    vendor_key_guess = guess_vendor_key_with_gemini(
                        item.description or "",
                        item.expense_date,
                        item.amount,
                        yaml_bases,
                    )
                    if vendor_key_guess:
                        llm_id_light = build_id_light_from_vendor(
                            vendor_key_guess,
                            exp_date,
                            amount,
                        )
                        if sys.stdin.isatty():
                            confirm = input(
                                f"Use LLM id_light {llm_id_light} [gemini]? (y/n): "
                            ).strip().lower()
                            if confirm == "y":
                                choice = llm_id_light
                                selected_source = "gemini"
                        else:
                            choice = llm_id_light
                            selected_source = "gemini"
                    if choice == "llm" and sys.stdin.isatty():
                        manual = input(
                            "Enter id_light manually (or blank to skip): "
                        ).strip()
                        if manual:
                            choice = manual
                            selected_source = "manual"

                if choice == "skip":
                    skipped_declined += 1
                    preview_lines.append(f"DECLINED id={item.row_id}")
                    continue

                if selected_source in {"gemini", "manual"} and item.description:
                    try:
                        print("Adding id_lite.yaml pattern for this description...")
                        appended = append_yaml_pattern(
                            yaml_path,
                            manual_id_light=choice,
                            description=item.description,
                        )
                        if appended:
                            preview_lines.append(
                                f"YAML_ADDED id={item.row_id} base={choice}"
                            )
                        else:
                            preview_lines.append(
                                f"YAML_EXISTS id={item.row_id} base={choice}"
                            )
                    except Exception as exc:
                        preview_lines.append(
                            f"YAML_ERROR id={item.row_id} error={exc}"
                        )
                if (
                    item.reason == "mismatch"
                    and selected_source in {"report", "vendor-prefix"}
                    and item.description
                ):
                    try:
                        print("Learning pattern from mismatch...")
                        appended = append_yaml_pattern(
                            yaml_path,
                            manual_id_light=choice,
                            description=item.description,
                        )
                        if appended:
                            preview_lines.append(
                                f"YAML_ADDED id={item.row_id} base={choice}"
                            )
                        else:
                            preview_lines.append(
                                f"YAML_EXISTS id={item.row_id} base={choice}"
                            )
                    except Exception as exc:
                        preview_lines.append(
                            f"YAML_ERROR id={item.row_id} error={exc}"
                        )
                if (
                    selected_source == "report"
                    and item.reason == "missing_id_light"
                    and item.description
                ):
                    try:
                        print("Adding id_lite.yaml pattern for report choice...")
                        appended = append_yaml_pattern(
                            yaml_path,
                            manual_id_light=choice,
                            description=item.description,
                        )
                        if appended:
                            preview_lines.append(
                                f"YAML_ADDED id={item.row_id} base={choice}"
                            )
                        else:
                            preview_lines.append(
                                f"YAML_EXISTS id={item.row_id} base={choice}"
                            )
                    except Exception as exc:
                        preview_lines.append(
                            f"YAML_ERROR id={item.row_id} error={exc}"
                        )

                cur.execute("SELECT id FROM expenses WHERE id_light = %s", (choice,))
                existing = cur.fetchone()
                if existing and existing[0] != item.row_id:
                    skipped_conflict += 1
                    preview_lines.append(
                        f"CONFLICT id={item.row_id} expected={choice} exists_on_id={existing[0]}"
                    )
                    try:
                        cur.execute(
                            "SELECT id_light, description, expense_date, amount FROM expenses WHERE id = %s",
                            (existing[0],),
                        )
                        existing_row = cur.fetchone()
                    except Exception:
                        existing_row = None
                    conflict_rows.append(
                        {
                            "row_id": item.row_id,
                            "expected_id_light": choice,
                            "existing_id": existing[0],
                            "existing_id_light": existing_row[0] if existing_row else "",
                            "description": item.description or "",
                            "expense_date": item.expense_date or "",
                            "amount": item.amount or "",
                            "existing_description": existing_row[1] if existing_row else "",
                            "existing_expense_date": existing_row[2] if existing_row else "",
                            "existing_amount": existing_row[3] if existing_row else "",
                        }
                    )
                    continue

                cur.execute(
                    "UPDATE expenses SET id_light = %s WHERE id = %s",
                    (choice, item.row_id),
                )
                conn.commit()
                updated += 1
                preview_lines.append(
                    f"UPDATED id={item.row_id} old={item.id_light} new={choice}"
                )
    finally:
        conn.commit()
        conn.close()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    preview_path = REPORT_DIR / f"id_light_mismatch_fix_preview_{timestamp}.txt"
    conflict_path = None
    if conflict_rows:
        conflict_path = REPORT_DIR / f"id_light_conflicts_{timestamp}.tsv"
        with conflict_path.open("w", encoding="utf-8") as handle:
            handle.write(
                "row_id\texpected_id_light\texisting_id\texisting_id_light\t"
                "description\texpense_date\tamount\t"
                "existing_description\texisting_expense_date\texisting_amount\n"
            )
            for row in conflict_rows:
                handle.write(
                    "\t".join(
                        [
                            str(row["row_id"]),
                            str(row["expected_id_light"]),
                            str(row["existing_id"]),
                            str(row["existing_id_light"]),
                            str(row["description"]),
                            str(row["expense_date"]),
                            str(row["amount"]),
                            str(row["existing_description"]),
                            str(row["existing_expense_date"]),
                            str(row["existing_amount"]),
                        ]
                    )
                    + "\n"
                )
    summary = [
        f"mismatches: {len(mismatches)}",
        f"updated: {updated}",
        f"skipped_conflict: {skipped_conflict}",
        f"skipped_declined: {skipped_declined}",
        f"recompute_warnings: {recompute_warnings}",
    ]
    if conflict_path:
        summary.append(f"conflicts_report: {conflict_path}")
    summary.append("")
    preview_path.write_text("\n".join(summary + preview_lines), encoding="utf-8")

    print(preview_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
