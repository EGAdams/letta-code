#!/usr/bin/env python3
"""Generate a styled HTML receipt match report from a TSV export."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


def build_html(df: pd.DataFrame, source_name: str) -> str:
    table = df.to_html(index=False, classes="data-table", escape=True)
    return f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<title>Receipt Match Report</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
  h1 {{ margin-bottom: 8px; }}
  .meta {{ color: #555; margin-bottom: 16px; }}
  table.data-table {{ border-collapse: collapse; width: 100%; }}
  table.data-table th, table.data-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  table.data-table th {{ background: #f5f5f5; position: sticky; top: 0; }}
  table.data-table tr:nth-child(even) {{ background: #fafafa; }}
  .section {{ margin-top: 18px; }}
  .callout {{ background: #f8fbff; border: 1px solid #cfe3ff; padding: 12px 14px; border-radius: 6px; }}
</style>
</head>
<body>
  <h1>Receipt Match Verification Report</h1>
  <div class=\"meta\">Purpose: verify receipt_url matches per expense id/id_light. • Rows: {len(df)}</div>

  <div class=\"section callout\">
    <strong>How to review:</strong>
    <ol>
      <li>Spot-check receipt_url paths to ensure they align with id_light/vendor.</li>
      <li>Mark any mismatches (wrong vendor/date/amount) for correction.</li>
      <li>After review, proceed to small-sample receipt scanning (5-10) and categorize fixes.</li>
    </ol>
  </div>

  <div class=\"section\">
    {table}
  </div>

  <div class=\"section callout\">
    <strong>Next steps:</strong>
    <ul>
      <li>Confirm mismatches to fix in receipt matching heuristics.</li>
      <li>Run Phase 2a sample scan (5-10 receipts).</li>
      <li>Update vendor/category mappings as needed.</li>
    </ul>
  </div>
</body>
</html>"""


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: make_receipt_match_html.py <input.tsv> <output.html>")
        return 2

    tsv = Path(sys.argv[1])
    out = Path(sys.argv[2])
    df = pd.read_csv(tsv, sep="\t", keep_default_na=False, na_filter=False)
    out.write_text(build_html(df, tsv.name), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())