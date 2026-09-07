"""HTTP boundary for an operator-approved Mazda Claude SDK repair."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, cast
from urllib.parse import quote


def build_repair_instruction(
    scanner: str, failure: str, document_path: str
) -> str:
    path = document_path or "(read it from this intake conversation)"
    return f"""The operator approved repair of this failed {scanner} scanner intake.
Failure shown in Last {scanner.title()} Scan: {failure}
Document path: {path}

Call run_claude_code_sdk exactly once with model='sonnet'. Give that SDK session the
failure above and instruct it to diagnose the cause, read the applicable AGENTS.md,
CLAUDE.md, skills and memory, implement the smallest correct fix in /home/adamsl/letta-code
or /home/adamsl/rol_finances, and run focused tests. Preserve unrelated working-tree work.
Do not launch an immediate retry if the SDK executor is busy, times out, or reports an
active run; report that condition instead.

The Claude SDK executor is containerized. Do not put a
/home/adamsl/rol_finances/.venv command in the SDK task or context because that host venv
cannot execute there. Tell the SDK session to use an interpreter available inside its
container and to report any verification limitation honestly. Tell it to end with
SDK_REPAIR_RESULT: PASSED only when the fix and its focused tests pass; otherwise it must
end with SDK_REPAIR_RESULT: FAILED.

Wait for run_claude_code_sdk to return before answering. Then summarize its verified result
in this same intake conversation and end your answer with exactly REPAIR_RESULT: PASSED or
REPAIR_RESULT: FAILED. PASSED is allowed only when the SDK tool returned successfully and
its focused verification passed."""


def response_used_sdk(response: object) -> bool:
    """True only when Mazda's response contains an actual SDK tool call."""
    if not isinstance(response, dict):
        return False
    response_map = cast(dict[str, object], response)
    messages_value = response_map.get("messages", [])
    if not isinstance(messages_value, list):
        return False
    messages = cast(list[object], messages_value)
    for message in messages:
        if not isinstance(message, dict):
            continue
        message_map = cast(dict[str, object], message)
        direct = message_map.get("tool_call")
        if isinstance(direct, dict) and cast(dict[str, object], direct).get(
            "name"
        ) == "run_claude_code_sdk":
            return True
        calls_value = message_map.get("tool_calls", [])
        if isinstance(calls_value, list):
            calls = cast(list[object], calls_value)
            if any(
                isinstance(call, dict)
                and cast(dict[str, object], call).get("name")
                == "run_claude_code_sdk"
                for call in calls
            ):
                return True
    return False


def _request_json(request: urllib.request.Request, timeout: float) -> object:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status // 100 != 2:
            raise RuntimeError(f"Request returned HTTP {response.status}")
        return cast(object, json.load(response))


def conversation_messages(
    letta_url: str, conversation_id: str, timeout: float = 30
) -> list[dict[str, Any]]:
    """Read the isolated Mazda conversation used by this scanner run."""
    request = urllib.request.Request(
        f"{letta_url.rstrip('/')}/v1/conversations/"
        f"{quote(conversation_id, safe='')}/messages?limit=200&order=asc",
        method="GET",
    )
    payload = _request_json(request, timeout)
    if isinstance(payload, list):
        values: object = cast(list[object], payload)
    elif isinstance(payload, dict):
        payload_map = cast(dict[str, object], payload)
        values = payload_map.get("messages", payload_map.get("results"))
    else:
        values = None
    if not isinstance(values, list):
        raise RuntimeError("Mazda conversation returned an invalid messages payload")
    value_list = cast(list[object], values)
    if not all(isinstance(item, dict) for item in value_list):
        raise RuntimeError("Mazda conversation returned an invalid messages payload")
    return cast(list[dict[str, Any]], value_list)


def sdk_activity(dashboard_url: str, timeout: float = 10) -> dict[str, Any]:
    """Read the dashboard's no-side-effect Claude SDK activity proxy."""
    request = urllib.request.Request(
        f"{dashboard_url.rstrip('/')}/api/claude-sdk-activity", method="GET"
    )
    payload = _request_json(request, timeout)
    if not isinstance(payload, dict):
        raise RuntimeError("Claude SDK activity endpoint returned an invalid payload")
    payload_map = cast(dict[str, object], payload)
    if not isinstance(payload_map.get("events"), list):
        raise RuntimeError("Claude SDK activity endpoint returned an invalid payload")
    if payload_map.get("ok") is not True:
        raise RuntimeError(
            str(payload_map.get("error") or "Claude SDK activity unavailable")
        )
    return cast(dict[str, Any], payload_map)


def send_mazda_repair(
    letta_url: str, conversation_id: str, message: str, timeout: float
) -> object:
    if not conversation_id:
        raise RuntimeError("Failed report did not expose its Mazda conversation id")
    payload = json.dumps({
        "messages": [{"role": "user", "content": message}],
        "streaming": False,
    }).encode()
    request = urllib.request.Request(
        f"{letta_url.rstrip('/')}/v1/conversations/"
        f"{quote(conversation_id, safe='')}/messages",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _request_json(request, timeout)
