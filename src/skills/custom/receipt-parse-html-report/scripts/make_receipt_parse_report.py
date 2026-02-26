#!/usr/bin/env python3
"""Generate a receipt parse HTML report with optional anomaly highlighting."""

from __future__ import annotations

import argparse
import json
import sys
import subprocess
from urllib.parse import unquote, urlparse
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

RECEIPTS_ROOT = Path("/home/adamsl/rol_finances/readable_documents/receipts")
REPORTS_ROOT = Path("/home/adamsl/rol_finances/readable_documents/reports")
LOGS_ROOT = REPORTS_ROOT / "logs"
PARSER_ROOT = Path(
    "/home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools"
)
PARSER_MODULE_PATH = PARSER_ROOT / "receipt_parsing_tools" / "parse_and_categorize.py"
ALLOWED_SUFFIXES = {".jpeg", ".jpg", ".png", ".pdf", ".tif", ".tiff"}

if not PARSER_MODULE_PATH.exists():
    raise RuntimeError(
        f"Receipt parser module not found: {PARSER_MODULE_PATH}. Fix this before running reports."
    )

parser_root_str = str(PARSER_ROOT)
if parser_root_str not in sys.path:
    sys.path.insert(0, parser_root_str)

try:
    from receipt_parsing_tools import parse_and_categorize as parser_module
except Exception as exc:  # pragma: no cover - hard error
    raise RuntimeError(
        "Failed to import receipt parser module from receipt_scanning_tools. "
        "Resolve the import error before proceeding."
    ) from exc


def format_markdown_table(rows: list[dict[str, str]]) -> str:
    headers = [
        "file_label",
        "status",
        "merchant",
        "date",
        "subtotal",
        "tax",
        "total",
        "items",
        "warnings",
        "model_name",
        "model_provider",
        "postprocessed",
        "anomalies",
        "anomaly_details",
        "second_engine",
        "second_status",
        "second_merchant",
        "second_date",
        "second_subtotal",
        "second_tax",
        "second_total",
        "second_model_name",
        "second_model_provider",
        "second_anomalies",
        "second_anomaly_details",
        "second_error",
        "vendor_key",
        "id_light",
        "error",
    ]
    display = {
        "file_label": "File",
        "status": "Status",
        "merchant": "Merchant",
        "date": "Date",
        "subtotal": "Subtotal",
        "tax": "Tax",
        "total": "Total",
        "items": "Items",
        "warnings": "Warnings",
        "model_name": "Model",
        "model_provider": "Provider",
        "postprocessed": "Postprocessed",
        "anomalies": "Anomalies",
        "anomaly_details": "Anomaly Details",
        "second_engine": "2nd Engine",
        "second_status": "2nd Status",
        "second_merchant": "2nd Merchant",
        "second_date": "2nd Date",
        "second_subtotal": "2nd Subtotal",
        "second_tax": "2nd Tax",
        "second_total": "2nd Total",
        "second_model_name": "2nd Model",
        "second_model_provider": "2nd Provider",
        "second_anomalies": "2nd Anomalies",
        "second_anomaly_details": "2nd Anomaly Details",
        "second_error": "2nd Error",
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


def parse_receipt(receipt_path: Path, engine: str) -> tuple[dict[str, Any] | None, str]:
    try:
        image_bytes = receipt_path.read_bytes()
    except Exception as exc:
        return None, f"Failed to read receipt bytes: {exc}"
    try:
        mime_type = parser_module._guess_mime(receipt_path)
        parsed = parser_module._parse_receipt(image_bytes, mime_type, engine)
    except Exception as exc:
        return None, f"Parser exception: {exc}"
    if parsed is None:
        return None, "Parser returned no data"

    try:
        payload = parser_module.to_primitive(parsed)
    except Exception as exc:
        return None, f"Failed to convert parser output: {exc}"

    if not isinstance(payload, dict):
        try:
            payload = dict(payload)
        except Exception:
            payload = {"result": payload}

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


def parse_subtotal(payload: dict[str, Any]) -> str:
    totals = payload.get("totals")
    if isinstance(totals, dict):
        subtotal = totals.get("subtotal")
        if subtotal is not None:
            return str(subtotal)
    return ""


def parse_tax(payload: dict[str, Any]) -> str:
    totals = payload.get("totals")
    if isinstance(totals, dict):
        tax_amount = totals.get("tax_amount")
        if tax_amount is not None:
            return str(tax_amount)
    return ""


def parse_model_name(payload: dict[str, Any]) -> str:
    meta = payload.get("meta")
    if isinstance(meta, dict):
        name = meta.get("model_name")
        if name:
            return str(name)
    return ""


def parse_model_provider(payload: dict[str, Any]) -> str:
    meta = payload.get("meta")
    if isinstance(meta, dict):
        provider = meta.get("model_provider")
        if provider:
            return str(provider)
    return ""


def parse_postprocessed(payload: dict[str, Any]) -> str:
    meta = payload.get("meta")
    if isinstance(meta, dict):
        value = meta.get("postprocessed_from_raw_text")
        if value is not None:
            return str(bool(value)).lower()
    return ""


def choose_second_engine(primary_engine: str) -> str | None:
    if primary_engine == "openai":
        return "gemini"
    if primary_engine in {"gemini", "auto", "local"}:
        return "openai"
    return None


def derive_vendor_key(id_light: str) -> str:
    tokens = [item for item in id_light.split("_") if item]
    if len(tokens) > 5:
        return "_".join(tokens[:-5])
    return id_light


def get_anomaly_flags(row: dict[str, str]) -> list[str]:
    flags, _ = get_anomaly_details(row)
    return flags


def get_anomaly_details(row: dict[str, str]) -> tuple[list[str], list[dict[str, str]]]:
    flags: list[str] = []
    details: list[dict[str, str]] = []
    provider = (row.get("model_provider") or "").strip().lower()
    model_name = (row.get("model_name") or "").strip().lower()
    is_local_engine = provider == "local" or "local" in model_name or (
        not provider and not model_name
    )
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
    subtotal_raw = row.get("subtotal", "")
    tax_raw = row.get("tax", "")
    total_raw = row.get("total", "")
    try:
        subtotal_val = float(subtotal_raw)
        tax_val = float(tax_raw)
        total_val = float(total_raw)
    except (TypeError, ValueError):
        subtotal_val = tax_val = total_val = None

    if subtotal_val is not None and tax_val is not None and total_val is not None:
        computed_total = subtotal_val + tax_val
        diff = abs(computed_total - total_val)
        if diff > 0.07:
            flags.append("total_mismatch")
            details.append(
                {
                    "field": "total",
                    "reason": "mismatch",
                    "value": total_raw,
                    "computed": f"{computed_total:.2f}",
                    "diff": f"{diff:.2f}",
                    "subtotal": f"{subtotal_val:.2f}",
                    "tax": f"{tax_val:.2f}",
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
        if reason == "mismatch":
            computed = item.get("computed", "")
            diff = item.get("diff", "")
            segments.append(
                f"{field}: mismatch (total={value} vs computed={computed}, diff={diff})"
            )
            continue
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
            "subtotal": "",
            "tax": "",
            "total": "",
            "items": "",
            "warnings": "",
            "model_name": "",
            "model_provider": "",
            "postprocessed": "",
            "second_engine": "",
            "second_status": "",
            "second_merchant": "",
            "second_date": "",
            "second_subtotal": "",
            "second_tax": "",
            "second_total": "",
            "second_model_name": "",
            "second_model_provider": "",
            "second_anomalies": "",
            "second_anomaly_details": "",
            "second_error": "",
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
            "subtotal": parse_subtotal(payload),
            "tax": parse_tax(payload),
            "total": parse_total(payload),
            "items": parse_items_count(payload),
            "warnings": parse_warnings(payload),
            "model_name": parse_model_name(payload),
            "model_provider": parse_model_provider(payload),
            "postprocessed": parse_postprocessed(payload),
            "second_engine": "",
            "second_status": "",
            "second_merchant": "",
            "second_date": "",
            "second_subtotal": "",
            "second_tax": "",
            "second_total": "",
            "second_model_name": "",
            "second_model_provider": "",
            "second_anomalies": "",
            "second_anomaly_details": "",
            "second_error": "",
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
        f"<td>{html_escape(row.get('subtotal', ''))}</td>"
        f"<td>{html_escape(row.get('tax', ''))}</td>"
        f"<td>{html_escape(row['total'])}</td>"
        f"<td>{html_escape(row['items'])}</td>"
        f"<td>{html_escape(row['warnings'])}</td>"
        f"<td>{html_escape(row.get('model_name', ''))}</td>"
        f"<td>{html_escape(row.get('model_provider', ''))}</td>"
        f"<td>{html_escape(row.get('postprocessed', ''))}</td>"
        f"{anomalies_cell}"
        f"<td>{html_escape(row.get('second_engine', ''))}</td>"
        f"<td>{html_escape(row.get('second_status', ''))}</td>"
        f"<td>{html_escape(row.get('second_merchant', ''))}</td>"
        f"<td>{html_escape(row.get('second_date', ''))}</td>"
        f"<td>{html_escape(row.get('second_subtotal', ''))}</td>"
        f"<td>{html_escape(row.get('second_tax', ''))}</td>"
        f"<td>{html_escape(row.get('second_total', ''))}</td>"
        f"<td>{html_escape(row.get('second_model_name', ''))}</td>"
        f"<td>{html_escape(row.get('second_model_provider', ''))}</td>"
        f"<td>{html_escape(row.get('second_anomalies', ''))}</td>"
        f"<td>{html_escape(row.get('second_anomaly_details', ''))}</td>"
        f"<td>{html_escape(row.get('second_error', ''))}</td>"
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
        <th>Subtotal</th>
        <th>Tax</th>
        <th>Total</th>
        <th>Items</th>
        <th>Warnings</th>
        <th>Model</th>
        <th>Provider</th>
        <th>Postprocessed</th>
        {anomaly_header}
        <th>2nd Engine</th>
        <th>2nd Status</th>
        <th>2nd Merchant</th>
        <th>2nd Date</th>
        <th>2nd Subtotal</th>
        <th>2nd Tax</th>
        <th>2nd Total</th>
        <th>2nd Model</th>
        <th>2nd Provider</th>
        <th>2nd Anomalies</th>
        <th>2nd Anomaly Details</th>
        <th>2nd Error</th>
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


def output_log_path() -> Path:
    LOGS_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return LOGS_ROOT / f"receipt_parse_log_{stamp}.txt"


def log_line(handle, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    handle.write(f"[{timestamp}] {message}\n")
    handle.flush()


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
        "--engine",
        default="auto",
        help="Parser engine to use: auto, gemini, openai, or local (default: auto)",
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
    if args.file or args.engine in {"openai", "gemini", "auto"}:
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
    log_path = output_log_path()
    rows: list[dict[str, str]] = []
    with log_path.open("w", encoding="utf-8") as log_handle:
        log_line(log_handle, f"Engine: {args.engine}")
        log_line(log_handle, f"Receipts selected: {len(selected)}")
        for idx, receipt_path in enumerate(selected, start=1):
            log_line(log_handle, f"[{idx}/{len(selected)}] Parsing {receipt_path}")
            payload, error = parse_receipt(receipt_path, engine=args.engine)
            if error:
                log_line(log_handle, f"Primary parse error: {error}")
            row = to_row(
                receipt_path,
                payload,
                error,
                include_anomalies=args.anomalies,
                include_missing_id_light=args.include_missing_id_light,
            )
            if row is None:
                log_line(log_handle, "Row skipped (missing id_light)")
                continue
            if row.get("anomalies"):
                second_engine = choose_second_engine(args.engine)
                if second_engine:
                    log_line(log_handle, f"Running second engine: {second_engine}")
                    second_payload, second_error = parse_receipt(
                        receipt_path, engine=second_engine
                    )
                    if second_error:
                        log_line(log_handle, f"Second parse error: {second_error}")
                    if second_payload is None:
                        row["second_engine"] = second_engine
                        row["second_status"] = "error"
                        row["second_error"] = second_error
                    else:
                        row["second_engine"] = second_engine
                        row["second_status"] = "ok"
                        row["second_merchant"] = parse_merchant(second_payload)
                        row["second_date"] = str(
                            second_payload.get("transaction_date", "")
                        )
                        row["second_subtotal"] = parse_subtotal(second_payload)
                        row["second_tax"] = parse_tax(second_payload)
                        row["second_total"] = parse_total(second_payload)
                        row["second_model_name"] = parse_model_name(second_payload)
                        row["second_model_provider"] = parse_model_provider(second_payload)
                        row["second_anomalies"] = ", ".join(
                            get_anomaly_flags(row={
                                **row,
                                "merchant": parse_merchant(second_payload),
                                "date": str(second_payload.get("transaction_date", "")),
                                "subtotal": parse_subtotal(second_payload),
                                "tax": parse_tax(second_payload),
                                "total": parse_total(second_payload),
                                "model_name": parse_model_name(second_payload),
                                "model_provider": parse_model_provider(second_payload),
                            })
                        )
                        row["second_anomaly_details"] = format_anomaly_details(
                            get_anomaly_details({
                                **row,
                                "merchant": parse_merchant(second_payload),
                                "date": str(second_payload.get("transaction_date", "")),
                                "subtotal": parse_subtotal(second_payload),
                                "tax": parse_tax(second_payload),
                                "total": parse_total(second_payload),
                                "model_name": parse_model_name(second_payload),
                                "model_provider": parse_model_provider(second_payload),
                            })[1]
                        )
            rows.append(row)
        log_line(log_handle, "Parsing complete")

    html = build_html(rows, include_anomalies=args.anomalies)
    report_path = output_path()
    report_path.write_text(html, encoding="utf-8")
    print(report_path)
    print(f"Log: {log_path}")
    if args.summary_json:
        print(json.dumps({"rows": rows}, ensure_ascii=False, indent=2))
    if args.summary_markdown:
        print(format_markdown_table(rows))


if __name__ == "__main__":
    main()