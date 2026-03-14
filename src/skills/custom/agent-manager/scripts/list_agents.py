#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = "http://10.0.0.143:8283"
DEFAULT_SETTINGS_PATH = os.path.expanduser("~/.letta/settings.json")


def load_settings() -> dict:
    try:
        with open(DEFAULT_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def resolve_base_url(args: argparse.Namespace, settings: dict) -> str:
    if args.base_url:
        return args.base_url
    env_url = os.environ.get("LETTA_BASE_URL")
    if env_url:
        return env_url
    sessions = settings.get("sessionsByServer") or {}
    if sessions:
        server = next(iter(sessions.keys()), None)
        if server:
            if server.startswith("http://") or server.startswith("https://"):
                return server
            return f"http://{server}"
    return DEFAULT_BASE_URL


def resolve_api_key(args: argparse.Namespace, settings: dict) -> str | None:
    if args.api_key:
        return args.api_key
    env_key = os.environ.get("LETTA_API_KEY")
    if env_key:
        return env_key
    env_settings = settings.get("env") or {}
    key = env_settings.get("LETTA_API_KEY")
    return key


def build_params(args: argparse.Namespace) -> dict:
    params = {}
    if args.name:
        params["name"] = args.name
    if args.query:
        params["query_text"] = args.query
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        if tags:
            params["tags"] = tags
            if args.match_all_tags:
                params["match_all_tags"] = True
    if args.include_blocks:
        params["include"] = ["agent.blocks"]
    if args.limit is not None:
        params["limit"] = args.limit
    return params


def build_url(base_url: str, params: dict) -> str:
    base = base_url.rstrip("/") + "/v1/agents/"
    if not params:
        return base
    query = urllib.parse.urlencode(params, doseq=True)
    return f"{base}?{query}"


def fetch(url: str, api_key: str | None) -> dict:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read().decode("utf-8")
    return json.loads(data)


def fmt_tags(tags: list | None) -> str:
    if not tags:
        return "-"
    return ",".join(tags)


def print_table(items: list[dict]) -> None:
    if not items:
        print("No agents found.")
        return
    headers = ["id", "name", "tags"]
    rows = []
    for item in items:
        rows.append([
            item.get("id", "-"),
            item.get("name", "-"),
            fmt_tags(item.get("tags")),
        ])
    widths = [max(len(str(r[i])) for r in ([headers] + rows)) for i in range(len(headers))]
    fmt = "  ".join([f"{{:{w}}}" for w in widths])
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for row in rows:
        print(fmt.format(*row))


def main() -> int:
    parser = argparse.ArgumentParser(description="List/search Letta agents via /v1/agents")
    parser.add_argument("--name", help="Exact name match")
    parser.add_argument("--query", help="Fuzzy search by name")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--match-all-tags", action="store_true", help="Require ALL tags")
    parser.add_argument("--include-blocks", action="store_true", help="Include agent.blocks")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--json", action="store_true", help="Print raw JSON")
    parser.add_argument("--base-url", help="Override base URL")
    parser.add_argument("--api-key", help="Override API key")

    args = parser.parse_args()
    settings = load_settings()
    base_url = resolve_base_url(args, settings)
    api_key = resolve_api_key(args, settings)
    params = build_params(args)
    url = build_url(base_url, params)

    try:
        result = fetch(url, api_key)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        msg = f"HTTP {exc.code}: {body or exc.reason}"
        if exc.code == 401 and not api_key:
            msg += " (no api key provided)"
        print(msg, file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    if isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        items = result.get("data") or result.get("agents") or result.get("items")
    else:
        items = None

    if items is None:
        print(json.dumps(result, indent=2))
        return 0

    print_table(items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())