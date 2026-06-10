"""Adapter around the Letta HTTP API.

A thin seam so the cleanup strategy never touches urllib directly and tests can
inject a fake with the same three methods.
"""
import json
import urllib.request
from urllib.parse import quote


class LettaClient:
    def __init__(self, base_url, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ── low-level ─────────────────────────────────────────────────────────────
    def _request(self, method, path, payload=None, timeout=None):
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        req = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
            body = resp.read().decode()
        return json.loads(body) if body else {}

    # ── high-level ────────────────────────────────────────────────────────────
    def clear_messages(self, agent_id):
        """Reset the agent's conversation so each cleanup starts fresh (Q3)."""
        path = f"/v1/agents/{agent_id}/messages/clear?agent_id={quote(agent_id, safe='')}"
        try:
            self._request("POST", path, payload={})
        except Exception:
            pass  # a failed reset must never block the actual cleanup

    def send_message(self, agent_id, text):
        return self._request(
            "POST",
            f"/v1/agents/{agent_id}/messages",
            payload={"messages": [{"role": "user", "content": text}], "stream": False},
        )

    def resolve_agent_id(self, name):
        data = self._request("GET", "/v1/agents?limit=200", timeout=10)
        agents = data if isinstance(data, list) else data.get("agents", [])
        for agent in agents:
            if agent.get("name") == name:
                return agent.get("id")
        return None
