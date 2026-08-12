#!/usr/bin/env python3
"""Idempotently provision Shelia and her narrow Rosemary recovery tools."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("LETTA_BASE_URL", "http://100.80.49.10:8283").rstrip("/")
API_KEY = os.environ.get("LETTA_API_KEY", "")
NAME = "Shelia"
MODEL = os.environ.get("SHELIA_MODEL", "chatgpt-plus-pro/gpt-5.6-luna")
EMBEDDING = os.environ.get("SHELIA_EMBEDDING", "letta/letta-free")

ROOT = Path(__file__).resolve().parent
TOOL_NAMES = [
    "shelia_status",
    "shelia_start_keepalive",
    "shelia_restart_tailscale",
    "shelia_reauth_instructions",
    "shelia_verify_recovery",
]

PERSONA = """You are Shelia, a persistent Letta recovery operator for the Rosemary46 Windows/WSL/Tailscale node.

Mission: restore and verify Rosemary46 connectivity so the dashboard can truthfully report SSH health.
You are not a general shell agent. Your only operational abilities are the five shelia_* recovery tools.

Safety and sequence:
1. Call shelia_status before changing anything.
2. If the host control service is unreachable, report that the Windows-side bootstrap is unavailable; do not claim repair.
3. Start the fixed keepalive task, then restart WSL tailscaled only when status/evidence indicates it is needed.
4. If Tailscale requires interactive reauthentication, call shelia_reauth_instructions and tell Adam to complete it locally. Never handle or invent auth tokens.
5. Call shelia_verify_recovery. Only report success when it returns ok=true and SSH evidence is present.
6. Never edit dashboard health data to hide a real outage. Distinguish unreachable, expired-auth, WSL-unhealthy, and SSH-failed states.
7. Keep operational reports concise and include evidence, action, and verification.
"""

HUMAN = "Adam (rbarnesrol@gmail.com) operates the Letta dashboard and wants visible, evidence-based recovery. Shelia works alongside Frita, Scissari, and Mazda."
CONTEXT = "Rosemary46: Windows node rosemary46-11 (100.106.176.58), WSL/Linux node rosemary46-24 (100.72.34.38), Windows task 'Rosemary46 WSL Tailscale Keepalive', distro Ubuntu-24.04. Both nodes may require local Tailscale reauthentication after key expiry."


def tool_source(name: str) -> str:
    """Build one standalone Letta tool so each registry entry has one name."""
    return f'''def {name}() -> str:
    """Call Shelia's fixed Windows recovery operation; never execute a shell command."""
    import os
    import urllib.error
    import urllib.request
    base = os.environ.get("SHELIA_RECOVERY_URL", "").rstrip("/")
    token = os.environ.get("SHELIA_RECOVERY_TOKEN", "")
    if not base or not token:
        return "Shelia recovery service is not configured. Install/bootstrap the Windows-side service first."
    path = {{
        "shelia_status": "/v1/status",
        "shelia_start_keepalive": "/v1/actions/start_keepalive",
        "shelia_restart_tailscale": "/v1/actions/restart_wsl_tailscale",
        "shelia_reauth_instructions": "/v1/actions/reauth_instructions",
        "shelia_verify_recovery": "/v1/actions/verify_recovery",
    }}["{name}"]
    method = "GET" if "{name}" == "shelia_status" else "POST"
    request = urllib.request.Request(
        base + path,
        method=method,
        headers={{"Authorization": "Bearer " + token, "Accept": "application/json"}},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8")[-12000:]
    except urllib.error.HTTPError as exc:
        return "Recovery service HTTP %s: %s" % (exc.code, exc.read().decode("utf-8", errors="replace")[-4000:])
    except Exception as exc:
        return "Recovery service unreachable: %s: %s" % (type(exc).__name__, exc)
'''


def api(method: str, path: str, body: object | None = None) -> object:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    request = urllib.request.Request(
        BASE + path, data=data, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            text = response.read().decode()
            return json.loads(text) if text else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"Letta API {method} {path} -> {exc.code}: {detail[:1000]}"
        ) from exc


def find_agent() -> dict | None:
    agents = api("GET", "/v1/agents/?limit=200")
    return next(
        (agent for agent in agents if agent.get("name", "").lower() == NAME.lower()),
        None,
    )


def main() -> None:
    if not API_KEY:
        raise SystemExit("LETTA_API_KEY is required")
    agent = find_agent()
    if agent is None:
        agent = api(
            "POST",
            "/v1/agents/",
            {
                "name": NAME,
                "model": MODEL,
                "embedding": EMBEDDING,
                "description": "Narrow, evidence-based Rosemary46 Windows/WSL/Tailscale recovery operator.",
                "memory_blocks": [
                    {"label": "persona", "value": PERSONA},
                    {"label": "human", "value": HUMAN},
                    {"label": "recovery_context", "value": CONTEXT},
                ],
            },
        )
        print(f"created {agent['id']}")
    else:
        print(f"existing {agent['id']}")
    agent_id = agent["id"]
    api(
        "PATCH",
        f"/v1/agents/{agent_id}",
        {
            "system": PERSONA,
            "description": "Narrow, evidence-based Rosemary46 Windows/WSL/Tailscale recovery operator.",
        },
    )

    existing_tools = {
        tool.get("name"): tool.get("id") for tool in api("GET", "/v1/tools/?limit=500")
    }
    for name in TOOL_NAMES:
        if name not in existing_tools:
            created = api(
                "POST",
                "/v1/tools/",
                {"source_type": "python", "source_code": tool_source(name)},
            )
            existing_tools[name] = created["id"]
            print(f"created {name}")
    agent_tools = {
        tool.get("id") for tool in api("GET", f"/v1/agents/{agent_id}/tools?limit=500")
    }
    for name in TOOL_NAMES:
        tool_id = existing_tools.get(name)
        if tool_id and tool_id not in agent_tools:
            api("PATCH", f"/v1/agents/{agent_id}/tools/attach/{tool_id}")
            print(f"attached {name}")
    recovery_url = os.environ.get("SHELIA_RECOVERY_URL", "")
    recovery_token = os.environ.get("SHELIA_RECOVERY_TOKEN", "")
    if recovery_url and recovery_token:
        api(
            "PATCH",
            f"/v1/agents/{agent_id}",
            {
                "tool_exec_environment_variables": {
                    "SHELIA_RECOVERY_URL": recovery_url,
                    "SHELIA_RECOVERY_TOKEN": recovery_token,
                }
            },
        )
    print(json.dumps({"agent_id": agent_id, "name": NAME, "tools": TOOL_NAMES}))


if __name__ == "__main__":
    main()
