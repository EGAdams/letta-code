---
name: irs-tax-document-routing
description: Routes IRS tax documents (including Form 9325 acknowledgements) to specialist IRS agents instead of receipt/expense ingestion. Use when classification indicates IRS/tax content or routing_key tax.irs_*.
---

# IRS Tax Document Routing

Use this skill when a scanned/ingested file appears to be an IRS tax document.

## Trigger conditions
- classifier returns `routing_key` starting with `tax.irs_`
- document contains IRS language (Internal Revenue Service, Form 9325)

## Routing policy
1. Do **not** route IRS tax docs into receipt/expense insertion.
2. Route to `irs-tax-document-router` agent.
3. For Form 9325, route to `irs-form-9325-expert`.

## Handoff payload shape
Use a structured payload with:
- file path
- sha256 (if available)
- routing key
- confidence
- classification reasons

## Helper script
Use `scripts/route_irs_tax_doc.py` to emit a normalized payload for routing.
