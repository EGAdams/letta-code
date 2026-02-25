#!/usr/bin/env python3
"""Generate a receipt parse HTML report with optional anomaly highlighting."""

from __future__ import annotations

import argparse
import json
import subprocess
from urllib.parse import unquote, urlparse
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

RECEIPTS_ROOT = Path("/home/adamsl/rol_finances/readable_documents/receipts")
REPORTS_ROOT = Path("/home/adamsl/rol_finances/readable_documents/reports")
PARSER_SCRIPT = Path(
    "/home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/receipt_parsing_tools/parse_and_categorize.py"
)
ALLOWED_SUFFIXES = {".jpeg", ".jpg", ".png", ".pdf", ".tif", ".tiff"}


def format_markdown_table(rows: list[dict[str, str]]) -> str:
    headers = [
        "file_label",
        "status",
        "merchant",
        "date",
        "total",
        "items",
        "warnings",
        "anomalies",
        "anomaly_details",
        "vendor_key",
        "id_light",
        "error",
    ]
    display = {
        "file_label": "File",
        "status": "Status",
        "merchant": "Merchant",
        "date": "Date",
        "total": "Total",
        "items": "Items",
        "warnings": "Warnings",
        "anomalies": "Anomalies",
        "anomaly_details": "Anomaly Details",
        "vendor_key": "Vendor Key",
        "id_light": "ID Light",
        "error": "Error",
    }
    lines = [
        "| " + " | ".join(display[key] for key in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = [row.get(key, "") for key in headers]
        values = [value.replace("\n", " ") if isinstance(value, str) else str(value) for value in values]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def html_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def iter_receipts(root: Path) -> Iterator[Path]:
    if not root.exists() or not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES:
            yield path


def choose_receipts(search_root: Path, limit: int | None) -> list[Path]:
    selected: list[Path] = []
    max_count = limit if limit is not None and limit > 0 else None
    for path in iter_receipts(search_root):
        selected.append(path)
        if max_count is not None and len(selected) >= max_count:
            break
    return selected


def normalize_file_arg(value: str) -> Path:
    parsed = urlparse(value)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
        if path.startswith("/Ubuntu-24.04/"):
            path = path[len("/Ubuntu-24.04") :]
        return Path(path)
    return Path(value)


def parse_receipt(receipt_path: Path) -> tuple[dict[str, Any] | None, str]:
    command = [
        "python3",
        str(PARSER_SCRIPT),
        "--file",
        str(receipt_path),
        "--engine",
        "local",
        "--json",
        "--no-pick",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except Exception as exc:
        return None, str(exc)
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        return None, stderr or stdout or "Parser command failed"
    if not stdout:
        return None, stderr or "Empty parser output"
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return None, f"JSON decode error: {exc}"
    return payload, ""


def build_file_url(path: Path) -> str:
    return f"file://wsl.localhost/Ubuntu-24.04{path.as_posix()}"


def parse_items_count(payload: dict[str, Any]) -> str:
    items = payload.get("items")
    if isinstance(items, list):
        return str(len(items))
    return "0"


def parse_warnings(payload: dict[str, Any]) -> str:
    warnings = payload.get("warnings")
    if isinstance(warnings, list):
        return "; ".join(str(item) for item in warnings)
    if isinstance(warnings, str):
        return warnings
    return ""


def parse_merchant(payload: dict[str, Any]) -> str:
    party = payload.get("party")
    if isinstance(party, dict):
        merchant_name = party.get("merchant_name")
        if merchant_name:
            return str(merchant_name)
    return ""


def parse_total(payload: dict[str, Any]) -> str:
    totals = payload.get("totals")
    if isinstance(totals, dict):
        total_amount = totals.get("total_amount")
        if total_amount is not None:
            return str(total_amount)
    return ""


def parse_raw_snippet(payload: dict[str, Any]) -> str:
    meta = payload.get("meta")
    if isinstance(meta, dict):
        raw_text = meta.get("raw_text")
        if raw_text:
            flat = " ".join(str(raw_text).split())
            return flat[:180]
    return ""


def derive_vendor_key(id_light: str) -> str:
    tokens = [item for item in id_light.split("_") if item]
    if len(tokens) > 5:
        return "_".join(tokens[:-5])
    return id_light


def tooltip_text(vendor_key: str, id_light: str) -> str:
    return f"Vendor Key: {vendor_key}\n\nID Lite: {id_light}"


def get_anomaly_flags(row: dict[str, str]) -> list[str]:
    flags, _ = get_anomaly_details(row)
    return flags


def get_anomaly_details(row: dict[str, str]) -> tuple[list[str], list[dict[str, str]]]:
    flags: list[str] = []
    details: list[dict[str, str]] = []
    merchant_raw = row.get("merchant", "")
    merchant = merchant_raw.strip().lower()
    merchant_len = len(merchant)
    merchant_alpha = sum(ch.isalpha() for ch in merchant)
    if not merchant or merchant in {"unknown", "n/a"}:
        flags.append("merchant_missing")
        details.append(
            {
                "field": "merchant",
                "reason": "missing",
                "value": merchant_raw,
                "length": str(merchant_len),
                "alpha_count": str(merchant_alpha),
            }
        )
    if merchant:
        if len(merchant) < 3:
            flags.append("merchant_too_short")
            details.append(
                {
                    "field": "merchant",
                    "reason": "too_short",
                    "value": merchant_raw,
                    "length": str(merchant_len),
                }
            )
        if sum(ch.isalpha() for ch in merchant) <= 2:
            flags.append("merchant_low_alpha")
            details.append(
                {
                    "field": "merchant",
                    "reason": "low_alpha",
                    "value": merchant_raw,
                    "alpha_count": str(merchant_alpha),
                }
            )
        junk_markers = {
            "today on aol",
            "aol",
            "inbox",
            "unread",
            "spam",
            "trash",
            "drafts",
            "sent",
            "more",
        }
        if any(marker in merchant for marker in junk_markers):
            flags.append("merchant_junk_phrase")
            details.append(
                {
                    "field": "merchant",
                    "reason": "junk_phrase",
                    "value": merchant_raw,
                }
            )
    total_raw = row.get("total", "")
    total_text = total_raw.strip()
    if not total_text or total_text in {"0", "0.0", "0.00"}:
        flags.append("total_missing")
        details.append(
            {
                "field": "total",
                "reason": "missing",
                "value": total_raw,
            }
        )
    date_raw = row.get("date", "")
    date_text = date_raw.strip()
    if not date_text:
        flags.append("date_missing")
        details.append(
            {
                "field": "date",
                "reason": "missing",
                "value": date_raw,
            }
        )
    raw_text_value = row.get("raw_snippet", "")
    raw_text = raw_text_value.strip()
    if not raw_text:
        flags.append("raw_snippet_empty")
        details.append(
            {
                "field": "raw_snippet",
                "reason": "empty",
                "value": raw_text_value,
                "length": str(len(raw_text_value)),
            }
        )
    return flags, details


def format_anomaly_details(details: list[dict[str, str]]) -> str:
    if not details:
        return ""
    segments: list[str] = []
    for item in details:
        field = item.get("field", "")
        reason = item.get("reason", "")
        value = item.get("value", "")
        extras = [
            f"len={item['length']}" for item in [item] if item.get("length")
        ] + [
            f"alpha={item['alpha_count']}" for item in [item] if item.get("alpha_count")
        ]
        extra_text = f" [{' '.join(extras)}]" if extras else ""
        if value:
            segments.append(f"{field}: {reason} ({value}){extra_text}")
        else:
            segments.append(f"{field}: {reason}{extra_text}")
    return "; ".join(segments)


def resolve_id_light(payload: dict[str, Any] | None) -> str:
    if payload is None:
        return ""
    candidates = [
        payload.get("id_light"),
        payload.get("receipt_metadata", {}).get("id_light") if isinstance(payload.get("receipt_metadata"), dict) else None,
        payload.get("meta", {}).get("id_light") if isinstance(payload.get("meta"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def to_row(
    path: Path,
    payload: dict[str, Any] | None,
    error: str,
    include_anomalies: bool,
    include_missing_id_light: bool,
) -> dict[str, str] | None:
    file_url = build_file_url(path)
    id_light = resolve_id_light(payload)
    if not id_light and not include_missing_id_light:
        return None
    if not id_light and include_missing_id_light:
        id_light = path.stem
    if not id_light:
        id_light = path.stem
    vendor_key = derive_vendor_key(id_light)
    if payload is None:
        row = {
            "file": file_url,
            "file_label": path.name,
            "status": "error",
            "merchant": "",
            "date": "",
            "total": "",
            "items": "",
            "warnings": "",
            "raw_snippet": "",
            "error": error,
            "id_light": id_light,
            "vendor_key": vendor_key,
        }
    else:
        row = {
            "file": file_url,
            "file_label": path.name,
            "status": "ok",
            "merchant": parse_merchant(payload),
            "date": str(payload.get("transaction_date", "")),
            "total": parse_total(payload),
            "items": parse_items_count(payload),
            "warnings": parse_warnings(payload),
            "raw_snippet": parse_raw_snippet(payload),
            "error": "",
            "id_light": id_light,
            "vendor_key": vendor_key,
        }

    if include_anomalies:
        anomalies, anomaly_details = get_anomaly_details(row)
        row["anomalies"] = ", ".join(anomalies)
        row["anomaly_details"] = format_anomaly_details(anomaly_details)
        row["anomalies_structured"] = anomaly_details
    else:
        row["anomalies"] = ""
        row["anomaly_details"] = ""
    return row


def build_row_html(row: dict[str, str], include_anomalies: bool) -> str:
    file_html = f'<a href="{html_escape(row["file"])}">{html_escape(row["file_label"])}</a>'
    raw_text = html_escape(row["raw_snippet"])
    tip = html_escape(tooltip_text(row["vendor_key"], row["id_light"]))
    anomaly_class = " anomaly" if include_anomalies and row.get("anomalies") else ""
    anomalies_cell = (
        f"<td>{html_escape(row['anomalies'])}</td><td>{html_escape(row.get('anomaly_details', ''))}</td>"
        if include_anomalies
        else ""
    )
    return (
        f"<tr class=\"{anomaly_class.strip()}\">"
        f"<td>{file_html}</td>"
        f"<td>{html_escape(row['status'])}</td>"
        f"<td>{html_escape(row['merchant'])}</td>"
        f"<td>{html_escape(row['date'])}</td>"
        f"<td>{html_escape(row['total'])}</td>"
        f"<td>{html_escape(row['items'])}</td>"
        f"<td>{html_escape(row['warnings'])}</td>"
        f'<td class="tooltip" data-tooltip="{tip}">{raw_text}</td>'
        f"{anomalies_cell}"
        f"<td>{html_escape(row['error'])}</td>"
        "</tr>"
    )


def build_html(rows: list[dict[str, str]], include_anomalies: bool) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body_rows = "\n".join(build_row_html(row, include_anomalies) for row in rows)
    anomaly_header = "<th>Anomalies</th><th>Anomaly Details</th>" if include_anomalies else ""
    anomaly_style = (
        "tr.anomaly { background: #fff4f4; }" if include_anomalies else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Receipt Parse Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f4f6; }}
    tr:nth-child(even) {{ background: #f9fafb; }}
    {anomaly_style}
    .tooltip {{ position: relative; cursor: help; }}
    .tooltip:hover::after {{
      content: attr(data-tooltip);
      position: absolute;
      right: 100%;
      left: auto;
      top: 0;
      margin-right: 8px;
      margin-top: 0;
      white-space: pre-line;
      background: #111827;
      color: #ffffff;
      padding: 8px 10px;
      border-radius: 6px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.20);
      z-index: 20;
      min-width: 260px;
      max-width: 560px;
    }}
  </style>
</head>
<body>
  <h1>Receipt Parse Report</h1>
  <p>Generated: {html_escape(generated_at)}</p>
  <table>
    <thead>
      <tr>
        <th>File</th>
        <th>Status</th>
        <th>Merchant</th>
        <th>Date</th>
        <th>Total</th>
        <th>Items</th>
        <th>Warnings</th>
        <th>Raw snippet</th>
        {anomaly_header}
        <th>Error</th>
      </tr>
    </thead>
    <tbody>
{body_rows}
    </tbody>
  </table>
</body>
</html>
"""


def output_path() -> Path:
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return REPORTS_ROOT / f"receipt_parse_sample_3_{stamp}.html"


def resolve_subdir(subdir: str) -> Path:
    target = (RECEIPTS_ROOT / subdir).resolve()
    receipts_root = RECEIPTS_ROOT.resolve()
    try:
        target.relative_to(receipts_root)
    except ValueError as exc:
        raise ValueError("--subdir must be relative to receipts root") from exc
    if not target.exists() or not target.is_dir():
        raise ValueError(f"Subdirectory not found: {subdir}")
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate receipt parse HTML report")
    parser.add_argument(
        "--file",
        action="append",
        help="Receipt file path or file:// URL (repeatable)",
    )
    parser.add_argument(
        "--subdir",
        help="Subdirectory under receipts root to search",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of receipts to include",
    )
    parser.add_argument(
        "--anomalies",
        action="store_true",
        help="Highlight rows with missing merchant/date/total/raw snippet",
    )
    parser.add_argument(
        "--include-missing-id-light",
        action="store_true",
        help="Include receipts that do not have id_light in parser output",
    )
    parser.add_argument(
        "--summary-json",
        action="store_true",
        help="Emit JSON summary of parsed rows to stdout",
    )
    parser.add_argument(
        "--summary-markdown",
        action="store_true",
        help="Emit a markdown table summary of parsed rows to stdout",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.file:
        args.include_missing_id_light = True
    if not args.anomalies:
        args.anomalies = True
    if not args.summary_json and not args.summary_markdown:
        args.summary_markdown = True
    selected: list[Path] = []
    if args.file:
        selected = [normalize_file_arg(value) for value in args.file]
    else:
        search_root = RECEIPTS_ROOT
        if args.subdir:
            try:
                search_root = resolve_subdir(args.subdir)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
        selected = choose_receipts(search_root=search_root, limit=args.limit)
    rows: list[dict[str, str]] = []
    for receipt_path in selected:
        payload, error = parse_receipt(receipt_path)
        row = to_row(
            receipt_path,
            payload,
            error,
            include_anomalies=args.anomalies,
            include_missing_id_light=args.include_missing_id_light,
        )
        if row is None:
            continue
        rows.append(row)

    html = build_html(rows, include_anomalies=args.anomalies)
    report_path = output_path()
    report_path.write_text(html, encoding="utf-8")
    print(report_path)
    if args.summary_json:
        print(json.dumps({"rows": rows}, ensure_ascii=False, indent=2))
    if args.summary_markdown:
        print(format_markdown_table(rows))


if __name__ == "__main__":
    main()