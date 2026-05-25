#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://100.80.49.10:8283"
SETTINGS_PATH = Path.home() / ".letta" / "settings.json"

AGENTS = {
    "Scissari": "agent-5955b0c2-7922-4ffe-9e43-b116053b80fa",
    "Hailey": "agent-2b4f760c-e22a-4b6a-9c8d-0ace7b9bac03",
}

REQUIRED_TOOLS = [
    "web_fetch_exa",
    "executor_run",
    "web_search_exa",
    "send_message_to_agent_async",
    "send_message_to_agent_and_wait_for_reply",
]


def load_settings() -> dict[str, Any]:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def resolve_base_url(args: argparse.Namespace, settings: dict[str, Any]) -> str:
    if args.base_url:
        return args.base_url.rstrip("/")
    if os.environ.get("LETTA_BASE_URL"):
        return os.environ["LETTA_BASE_URL"].rstrip("/")
    sessions = settings.get("sessionsByServer") or {}
    if sessions:
        server = next(iter(sessions.keys()))
        if server.startswith(("http://", "https://")):
            return server.rstrip("/")
        return f"http://{server}".rstrip("/")
    return DEFAULT_BASE_URL.rstrip("/")


def resolve_api_key(args: argparse.Namespace, settings: dict[str, Any]) -> str:
    if args.api_key:
        return args.api_key
    if os.environ.get("LETTA_API_KEY"):
        return os.environ["LETTA_API_KEY"]
    return (settings.get("env") or {}).get("LETTA_API_KEY") or ""


class LettaApi:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def request(self, method: str, path: str) -> Any:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            self.base_url + path,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed: HTTP {exc.code}: {body}") from exc
        return json.loads(body) if body else None

    def list_agent_tools(self, agent_id: str) -> list[dict[str, Any]]:
        body = self.request("GET", f"/v1/agents/{agent_id}/tools")
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            return body.get("data") or body.get("items") or []
        return []

    def list_tools(self) -> list[dict[str, Any]]:
        body = self.request("GET", "/v1/tools/?limit=500")
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            return body.get("data") or body.get("items") or []
        return []

    def attach_tool(self, agent_id: str, tool_id: str) -> None:
        self.request("PATCH", f"/v1/agents/{agent_id}/tools/attach/{tool_id}")

    def detach_tool(self, agent_id: str, tool_id: str) -> None:
        self.request("PATCH", f"/v1/agents/{agent_id}/tools/detach/{tool_id}")


def resolve_required_tools(api: LettaApi) -> dict[str, dict[str, Any]]:
    tools = api.list_tools()
    by_name: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_TOOLS:
        matches = [tool for tool in tools if tool.get("name") == name]
        if not matches:
            raise RuntimeError(f"Required tool not found on server: {name}")
        by_name[name] = matches[0]
    return by_name


def ensure_agent(
    api: LettaApi,
    agent_name: str,
    agent_id: str,
    required_by_name: dict[str, dict[str, Any]],
    dry_run: bool,
    exact: bool,
) -> dict[str, Any]:
    before = api.list_agent_tools(agent_id)
    attached_names = {tool.get("name") for tool in before}
    missing = [name for name in REQUIRED_TOOLS if name not in attached_names]
    attached_now: list[str] = []
    extra_before = sorted(
        tool.get("name")
        for tool in before
        if tool.get("name") and tool.get("name") not in REQUIRED_TOOLS
    )
    detached_now: list[str] = []

    if not dry_run:
        for name in missing:
            api.attach_tool(agent_id, required_by_name[name]["id"])
            attached_now.append(name)
        if exact:
            for tool in before:
                tool_name = tool.get("name")
                tool_id = tool.get("id")
                if (
                    tool_name
                    and tool_id
                    and tool_name not in REQUIRED_TOOLS
                ):
                    api.detach_tool(agent_id, tool_id)
                    detached_now.append(tool_name)

    after = api.list_agent_tools(agent_id)
    after_names = [tool.get("name") for tool in after]
    still_missing = [name for name in REQUIRED_TOOLS if name not in set(after_names)]
    extra_after = sorted(
        tool.get("name")
        for tool in after
        if tool.get("name") and tool.get("name") not in REQUIRED_TOOLS
    )

    return {
        "agent": agent_name,
        "agent_id": agent_id,
        "had_before": sorted(name for name in attached_names if name),
        "missing_before": missing,
        "extra_before": extra_before,
        "attached_now": attached_now,
        "detached_now": detached_now,
        "still_missing": still_missing,
        "extra_after": extra_after,
        "ok": not still_missing and (not exact or not extra_after),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ensure Scissari and Hailey have their required shared tools."
    )
    parser.add_argument("--base-url", help="Letta API base URL")
    parser.add_argument("--api-key", help="Letta API key")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--exact",
        action="store_true",
        help="Detach any extra tools so the agent ends with exactly the required pairing set.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    api = LettaApi(
        resolve_base_url(args, settings),
        resolve_api_key(args, settings),
    )
    required_by_name = resolve_required_tools(api)
    results = [
        ensure_agent(api, name, agent_id, required_by_name, args.dry_run, args.exact)
        for name, agent_id in AGENTS.items()
    ]
    print(
        json.dumps(
            {"dry_run": args.dry_run, "exact": args.exact, "results": results},
            indent=2,
        )
    )
    return 0 if all(result["ok"] for result in results) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
