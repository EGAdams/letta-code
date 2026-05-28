#!/usr/bin/env python3
"""Bootstrap all ROL Finances agents on the current Letta server."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROLE_ROOT = Path("/home/adamsl/rol_finances")
REGISTRY_JSON = ROLE_ROOT / "external_agents" / "AGENT_REGISTRY.json"
REGISTRY_MD = ROLE_ROOT / "external_agents" / "AGENT_REGISTRY.md"
CREATE_SCRIPTS = {
    "irs-tax-document-router": ROLE_ROOT / "external_agents" / "create_irs_tax_router_agent.py",
    "irs-form-9325-expert": ROLE_ROOT / "external_agents" / "create_irs_form_9325_expert_agent.py",
    "moms-ledger-parser": ROLE_ROOT / "external_agents" / "create_moms_ledger_parser_agent.py",
    "orchestrator-quinn": ROLE_ROOT / "external_agents" / "create_orchestrator_agent.py",
    "tax-document-parsing-agent": ROLE_ROOT / "external_agents" / "create_tax_document_parsing_agent.py",
}

LIST_AGENTS = Path("/home/adamsl/letta-code/src/skills/custom/agent-manager/scripts/list_agents.py")


def load_registry() -> list[dict]:
    return json.loads(REGISTRY_JSON.read_text())


def list_agents() -> list[dict]:
    result = subprocess.run(
        ["python3", str(LIST_AGENTS), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    data = json.loads(result.stdout)
    if isinstance(data, dict):
        return data.get("data") or data.get("agents") or data.get("items") or []
    return data


def agent_exists(name: str, agents: list[dict]) -> dict | None:
    for agent in agents:
        if agent.get("name") == name:
            return agent
    return None


def run_create(script_path: Path) -> str:
    if not script_path.exists():
        raise RuntimeError(f"Missing create script: {script_path}")
    cmd = ["bash", "-lc", f"source {ROLE_ROOT}/.venv/bin/activate && python3 {script_path}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout.strip()


def update_registry_md(registry: list[dict]) -> None:
    lines = [
        "# Agent Registry (Central)",
        "",
        "Source: Letta `/v1/agents`",
        "",
        "## Purpose",
        "Single source of truth for agent IDs, names, canonical names, and lanes.",
        "",
        "## Naming convention",
        "- `<domain>-<function>-<role>` (e.g., `ledger-moms-parser`, `orchestrator-quinn`)",
        "- Keep IDs immutable; names can change, canonical_name tracks intended standard.",
        "",
        "## Agents",
        "",
        "| lane | canonical_name | current_name | agent_id | model |",
        "|---|---|---|---|---|",
    ]
    for item in registry:
        lines.append(
            f"| {item['lane']} | {item['canonical_name']} | {item['name']} | {item['id']} | {item['model']} |"
        )
    lines += [
        "",
        "## Coordination policy",
        "- Quinn orchestrates and delegates; specialists execute.",
        "- Keep this file updated after any create/rename/delete agent operation.",
        "- For memfs-backed durability, mirror summary into Letta memory files.",
    ]
    REGISTRY_MD.write_text("\n".join(lines) + "\n")


def main() -> int:
    registry = load_registry()
    agents = list_agents()

    updated = []
    for item in registry:
        name = item["name"]
        existing = agent_exists(name, agents)
        if existing:
            item["id"] = existing.get("id", item["id"])
            updated.append(item)
            continue
        script = CREATE_SCRIPTS.get(item["canonical_name"]) or CREATE_SCRIPTS.get(name)
        if script:
            run_create(script)
            # re-fetch agents and update
            agents = list_agents()
            existing = agent_exists(name, agents)
            if not existing:
                raise RuntimeError(f"Created {name} but it was not found on server")
            item["id"] = existing.get("id", item["id"])
        updated.append(item)

    REGISTRY_JSON.write_text(json.dumps(updated, indent=2) + "\n")
    update_registry_md(updated)
    print("Bootstrap complete. Updated AGENT_REGISTRY with current server IDs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
