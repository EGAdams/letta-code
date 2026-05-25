#!/usr/bin/env python3
"""Parse tax document folder using Gemini CLI (OAuth) and route to IRS router."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import subprocess

# Local imports from rol_finances project
sys.path.append("/home/adamsl/rol_finances")
import importlib.util
import hashlib
import os
import re

_GEMINI_CLI_PATH = Path("/home/adamsl/rol_finances/parsing_router/gemini_cli.py")
_gemini_spec = importlib.util.spec_from_file_location("gemini_cli", _GEMINI_CLI_PATH)
if _gemini_spec is None or _gemini_spec.loader is None:
    raise SystemExit(f"Unable to load gemini_cli from {_GEMINI_CLI_PATH}")
_gemini_mod = importlib.util.module_from_spec(_gemini_spec)
_gemini_spec.loader.exec_module(_gemini_mod)  # type: ignore[attr-defined]
is_gemini_cli_installed = _gemini_mod.is_gemini_cli_installed
run_gemini_prompt = _gemini_mod.run_gemini_prompt


def _run_gemini_with_files(
    prompt: str,
    *,
    model_candidates: list[str] | None,
    timeout_seconds: int,
    include_dir: Path,
) -> str:
    """Run gemini CLI with file access enabled for include_dir."""
    env = os.environ.copy()
    env.setdefault("CI", "1")
    env.setdefault("NO_COLOR", "1")

    candidates = [m for m in (model_candidates or []) if m]
    if not candidates:
        candidates = [
            os.getenv("GEMINI_MODEL"),
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ]
        candidates = [m for m in candidates if m]

    last_error: Exception | None = None
    for model_name in candidates:
        cmd = [
            "gemini",
            "--model",
            model_name,
            "--output-format",
            "json",
            "--include-directories",
            str(include_dir),
            "-p",
            prompt,
        ]
        try:
            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
                env=env,
                cwd=str(include_dir),
            )
        except subprocess.TimeoutExpired:
            last_error = RuntimeError(f"gemini CLI timed out for model {model_name}")
            continue

        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip() or f"exit code {result.returncode}"
            last_error = RuntimeError(f"gemini CLI failed for model {model_name}: {details}")
            continue

        raw = (result.stdout or "").strip()
        if raw:
            return raw
        last_error = RuntimeError(f"gemini CLI returned empty output for model {model_name}")

    if last_error is not None:
        raise last_error
    raise RuntimeError("No Gemini CLI model candidates available")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".pdf", ".tif", ".tiff"}


def sha256_for(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def pick_primary_file(folder: Path) -> Path | None:
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    if not files:
        return None
    ranked = sorted(files, key=lambda p: (0 if "form_" in p.name.lower() else 1, p.name.lower()))
    return ranked[0]


def infer_identity(folder_name: str) -> dict[str, Any]:
    m = re.search(r"_(front|back)_(\d+)$", folder_name, re.IGNORECASE)
    if not m:
        return {"side": None, "sequence": None, "paired_folder": None}
    side = m.group(1).lower()
    seq = int(m.group(2))
    paired_side = "back" if side == "front" else "front"
    paired = re.sub(r"_(front|back)_(\d+)$", f"_{paired_side}_{seq}", folder_name, flags=re.IGNORECASE)
    return {"side": side, "sequence": seq, "paired_folder": paired}

TAX_ROOT = Path("/home/adamsl/rol_finances/readable_documents/tax_documents")


PROMPT = """\
You are extracting structured information from an IRS or tax document image.

Return ONLY valid JSON with this schema:
{
  "classification": {
    "routing_key": "tax.irs_generic",
    "form_candidates": ["1040-SR"],
    "tax_year_candidates": ["2023"]
  },
  "parties": {
    "taxpayer_name": null,
    "spouse_name": null,
    "preparer": null,
    "address": null
  },
  "identifiers": {
    "ssn_masked": [],
    "ein_masked": [],
    "submission_id": [],
    "other_ids": []
  },
  "checkboxes": [
    {"field_name": "filing_status::Single", "value": "checked|unchecked|unknown", "confidence": 0.0, "evidence_text": "..."}
  ],
  "numeric_fields": [
    {"field_name": "currency_candidate", "raw_text": "$1,234.56", "normalized_value": 1234.56, "currency": "USD", "confidence": 0.0, "evidence_text": "..."}
  ],
  "line_items": [
    {"line_label": "Taxable income", "line_number": "15", "value": 78048, "confidence": 0.0, "evidence_text": "..."}
  ],
  "date_fields": [
    {"field_name": "date_candidate", "raw_text": "01/15/2024", "iso_date": "2024-01-15", "confidence": 0.0}
  ],
  "ocr_preview": "First ~40 lines of OCR text",
  "warnings": []
}

Guidelines:
- Use masked identifiers only (e.g., XXX-XX-1234).
- Populate form_candidates/tax_year_candidates from visible text.
- Add warnings for missing key sections or low confidence.
- Keep evidence_text short (<= 200 chars).
"""


def _json_from_response(text: str) -> dict[str, Any]:
    # strip code fences if any
    cleaned = text.replace("```json", "").replace("```", "").strip()
    # try to locate the first JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _parse_or_raise(raw_text: str, folder: Path) -> dict[str, Any]:
    if not raw_text or not raw_text.strip():
        raw_path = folder / "gemini_raw.txt"
        raw_path.write_text(raw_text or "")
        raise SystemExit(f"Gemini CLI returned empty output. See {raw_path}")

    try:
        return _json_from_response(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        raw_path = folder / "gemini_raw.txt"
        raw_path.write_text(raw_text)
        raise SystemExit(f"Gemini CLI returned non-JSON output. See {raw_path}")


def _write_detail(doc: dict[str, Any], preview_lines: list[str]) -> str:
    lines = [
        "# Document Detail",
        "",
        "## Identity",
        f"- document_folder: {doc['document_identity']['folder']}",
        f"- primary_file: {doc['document_identity']['filename']}",
        f"- sha256: {doc['document_identity']['sha256']}",
        f"- page_side: {doc['document_identity']['page_side']}",
        f"- sequence: {doc['document_identity']['sequence']}",
        f"- paired_folder: {doc['document_identity']['paired_folder']}",
        "",
        "## Source + metadata",
        f"- ocr_used: {doc['extraction_metadata']['ocr_used']}",
        f"- extractor_version: {doc['extraction_metadata']['extractor_version']}",
        f"- extracted_at_utc: {doc['extraction_metadata']['timestamp_utc']}",
        "",
        "## Parties",
        f"- taxpayer_name: {doc['parties'].get('taxpayer_name')}",
        f"- spouse_name: {doc['parties'].get('spouse_name')}",
        f"- preparer: {doc['parties'].get('preparer')}",
        f"- address: {doc['parties'].get('address')}",
        "",
        "## IDs",
        f"- ssn_masked: {', '.join(doc['identifiers']['ssn_masked']) if doc['identifiers']['ssn_masked'] else 'none'}",
        f"- ein_masked: {', '.join(doc['identifiers']['ein_masked']) if doc['identifiers']['ein_masked'] else 'none'}",
        f"- submission_id: {', '.join(doc['identifiers']['submission_id']) if doc['identifiers']['submission_id'] else 'none'}",
        "",
        "## Checkbox states",
        _rows(doc["checkboxes"], ["field_name", "value", "confidence", "evidence_text"]),
        "",
        "## Numeric fields",
        _rows(doc["numeric_fields"], ["field_name", "raw_text", "normalized_value", "currency", "confidence"]),
        "",
        "## Line items",
        _rows(doc["line_items"], ["line_label", "line_number", "value", "confidence", "evidence_text"]),
        "",
        "## Date fields",
        _rows(doc["date_fields"], ["field_name", "raw_text", "iso_date", "confidence"]),
        "",
        "## Calculation inputs",
    ]
    for k, v in doc["calculation_inputs"].items():
        lines.append(f"- {k}: {v}")
    lines += [
        "",
        "## Data quality warnings",
    ]
    if doc["extraction_metadata"]["warnings"]:
        for w in doc["extraction_metadata"]["warnings"]:
            lines.append(f"- {w}")
    else:
        lines.append("- none")

    lines += [
        "",
        "## OCR evidence preview",
        "```",
        "\n".join(preview_lines[:40]),
        "```",
        "",
    ]
    return "\n".join(lines)


def _rows(items: list[dict[str, Any]], cols: list[str]) -> str:
    if not items:
        return "- none\n"
    header = "| " + " | ".join(cols) + " |\n"
    sep = "|" + "|".join(["---" for _ in cols]) + "|\n"
    body = ""
    for it in items[:200]:
        vals = [str(it.get(c, "")) for c in cols]
        body += "| " + " | ".join(vals) + " |\n"
    return header + sep + body


def _summary(doc: dict[str, Any]) -> str:
    forms = ", ".join(doc["classification"]["form_candidates"]) or "none"
    years = ", ".join(doc["classification"]["tax_year_candidates"]) or "none"
    return "\n".join(
        [
            "# Document Summary",
            "",
            "## Identity",
            f"- document_folder: {doc['document_identity']['folder']}",
            f"- primary_file: {doc['document_identity']['filename']}",
            "",
            "## Classification",
            f"- routing_key: {doc['classification']['routing_key']}",
            f"- form_candidates: {forms}",
            "",
            "## Filing Period",
            f"- tax_year_candidates: {years}",
            "",
            "## Key Flags",
            f"- checkbox_fields_detected: {len(doc['checkboxes'])}",
            f"- numeric_fields_detected: {len(doc['numeric_fields'])}",
            "",
            "## One-line Description",
            "Gemini CLI extraction complete. See extracted_fields.json and detail.md.",
            "",
        ]
    )


def _build_calc_inputs(doc: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "primary_form": (doc["classification"]["form_candidates"] or [None])[0],
        "tax_year": (doc["classification"]["tax_year_candidates"] or [None])[0],
        "ssn_masked_primary": (doc["identifiers"]["ssn_masked"] or [None])[0],
        "checkbox_count": len(doc["checkboxes"]),
    }
    currency_vals = [
        n.get("normalized_value")
        for n in doc["numeric_fields"]
        if n.get("field_name") == "currency_candidate" and isinstance(n.get("normalized_value"), (int, float))
    ]
    if currency_vals:
        out["currency_values_detected"] = currency_vals[:50]
        out["currency_total_detected"] = round(sum(currency_vals), 2)
    return out


def resolve_folder(folder: str | None, file_path: str | None) -> Path:
    if folder:
        path = Path(folder).expanduser()
        if not path.exists():
            raise SystemExit(f"Folder not found: {path}")
        return path
    if file_path:
        fpath = Path(file_path).expanduser()
        if not fpath.exists():
            raise SystemExit(f"File not found: {fpath}")
        return fpath.parent
    raise SystemExit("Provide --folder or --file")


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse tax document folder using Gemini CLI")
    parser.add_argument("--folder")
    parser.add_argument("--file")
    parser.add_argument("--routing-key", default="tax.irs_generic")
    parser.add_argument("--confidence", type=float, default=0.0)
    parser.add_argument("--reason", action="append", default=[])
    parser.add_argument("--gemini-timeout", type=int, default=120)
    parser.add_argument("--gemini-model", action="append", default=[])
    parser.add_argument("--route-timeout", type=int, default=30)
    parser.add_argument("--skip-route", action="store_true")
    args = parser.parse_args()

    if not is_gemini_cli_installed():
        raise SystemExit("Gemini CLI is not installed or not on PATH")

    folder = resolve_folder(args.folder, args.file)
    primary = pick_primary_file(folder)
    if not primary:
        raise SystemExit(f"No primary image/pdf found in {folder}")

    prompt = (
        f"{PROMPT}\n\n"
        f"Image to analyze: @{primary}\n"
        "Return ONLY the JSON object."
    )
    model_candidates = args.gemini_model or None
    raw_text = _run_gemini_with_files(
        prompt,
        model_candidates=model_candidates,
        timeout_seconds=args.gemini_timeout,
        include_dir=folder,
    )
    parsed = _parse_or_raise(raw_text, folder)

    identity = infer_identity(folder.name)
    doc: dict[str, Any] = {
        "document_identity": {
            "folder": folder.name,
            "filename": primary.name,
            "file_path": str(primary),
            "sha256": sha256_for(primary),
            "page_side": identity["side"],
            "sequence": identity["sequence"],
            "paired_folder": identity["paired_folder"],
        },
        "classification": parsed.get("classification", {}),
        "parties": parsed.get("parties", {}),
        "identifiers": parsed.get("identifiers", {}),
        "checkboxes": parsed.get("checkboxes", []),
        "numeric_fields": parsed.get("numeric_fields", []),
        "line_items": parsed.get("line_items", []),
        "date_fields": parsed.get("date_fields", []),
        "calculation_inputs": {},
        "extraction_metadata": {
            "ocr_used": True,
            "extractor_version": "tax-doc-gemini-cli-v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "warnings": parsed.get("warnings", []),
        },
    }

    doc["classification"].setdefault("routing_key", args.routing_key)
    doc["classification"].setdefault("form_candidates", [])
    doc["classification"].setdefault("tax_year_candidates", [])

    doc["parties"].setdefault("taxpayer_name", None)
    doc["parties"].setdefault("spouse_name", None)
    doc["parties"].setdefault("preparer", None)
    doc["parties"].setdefault("address", None)

    identifiers = doc["identifiers"]
    identifiers.setdefault("ssn_masked", [])
    identifiers.setdefault("ein_masked", [])
    identifiers.setdefault("submission_id", [])
    identifiers.setdefault("other_ids", [])

    doc["classification"].setdefault("routing_key", args.routing_key)
    doc["classification"].setdefault("form_candidates", [])
    doc["classification"].setdefault("tax_year_candidates", [])

    doc["calculation_inputs"] = _build_calc_inputs(doc)

    preview_lines = (parsed.get("ocr_preview") or "").splitlines()
    if not preview_lines:
        preview_lines = ["(no OCR preview provided)"]

    (folder / "extracted_fields.json").write_text(json.dumps(doc, indent=2))
    (folder / "detail.md").write_text(_write_detail(doc, preview_lines))
    (folder / "summary.md").write_text(_summary(doc))

    routing_payload = {
        "file_path": str(primary),
        "filename": primary.name,
        "sha256": doc["document_identity"]["sha256"],
        "routing_key": doc["classification"]["routing_key"],
        "confidence": args.confidence,
        "reasons": args.reason,
    }
    (folder / "routing_payload.json").write_text(json.dumps(routing_payload, indent=2))

    if not args.skip_route:
        # Auto-route to IRS tax document router via letta CLI
        agent_id = os.getenv("IRS_TAX_ROUTER_AGENT_ID", "agent-2302eb3f-23a7-4695-9bd0-8903b0d2b02f")
        msg = (
            "New tax document parsed. Routing payload:\n\n"
            + json.dumps(routing_payload, indent=2)
        )
        cmd = [
            "/home/adamsl/letta-code/letta.js",
            "-p",
            "--agent",
            agent_id,
            msg,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=args.route_timeout,
            )
        except subprocess.TimeoutExpired:
            raise SystemExit(
                f"Routing timed out after {args.route_timeout}s."
            )
        if result.returncode != 0:
            raise SystemExit(
                f"Failed to route to IRS tax document router: {result.stderr or result.stdout}"
            )

    print(json.dumps({"folder": folder.name, "primary": primary.name}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
