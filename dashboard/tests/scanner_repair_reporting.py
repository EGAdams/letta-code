"""Render and verify Mazda/Claude repair telemetry for the terminal."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, cast

Emit = Callable[[str], None]


@dataclass(frozen=True)
class RepairOutcome:
    passed: bool
    detail: str
    sdk_run_id: str = ""


def pretty(value: object) -> str:
    if isinstance(value, str):
        try:
            return json.dumps(json.loads(value), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            return value
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def message_text(message: dict[str, Any]) -> str:
    for key in ("content", "reasoning", "tool_return"):
        value = message.get(key)
        if value not in (None, "", []):
            return pretty(value)
    return ""


def tool_call(message: dict[str, Any]) -> dict[str, Any] | None:
    direct = message.get("tool_call")
    if isinstance(direct, dict):
        return cast(dict[str, Any], direct)
    return None


def render_message(message: dict[str, Any], emit: Emit) -> None:
    kind = str(message.get("message_type") or "")
    call = tool_call(message)
    if kind == "tool_call_message" and call:
        name = str(call.get("name") or "tool")
        label = "Claude Code SDK" if name == "run_claude_code_sdk" else name
        emit(f"\nMazda -> {label}:\n{pretty(call.get('arguments', ''))}")
        return
    if kind == "tool_return_message":
        name = str(message.get("name") or "tool")
        label = (
            "Claude Code SDK -> Mazda (final output)"
            if name == "run_claude_code_sdk"
            else f"{name} -> Mazda"
        )
        emit(f"\n{label}:\n{message_text(message)}")
        for stream in ("stdout", "stderr"):
            value = message.get(stream)
            if value not in (None, "", []):
                emit(f"\n{label} {stream}:\n{pretty(value)}")
        return
    if kind == "reasoning_message":
        emit(f"\nMazda (reasoning):\n{message_text(message)}")
    elif kind == "assistant_message":
        emit(f"\nMazda:\n{message_text(message)}")


def render_activity(event: dict[str, Any], emit: Emit) -> None:
    category = str(event.get("category") or "activity")
    text = str(event.get("text") or "")
    if category == "tool_calls":
        emit(
            f"\nClaude Code SDK -> {event.get('tool') or text}:\n"
            f"{pretty(event.get('input', {}))}"
        )
    elif event.get("message_type") == "tool_result":
        suffix = " (ERROR)" if event.get("is_error") else ""
        emit(f"\nClaude Code SDK tool result{suffix}:\n{text}")
    else:
        emit(f"\nClaude Code SDK [{category}]:\n{text}")


def response_messages(response: object) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    value = cast(dict[str, Any], response).get("messages", [])
    if not isinstance(value, list):
        return []
    values = cast(list[object], value)
    return [cast(dict[str, Any], item) for item in values if isinstance(item, dict)]


def _sdk_model(call_message: dict[str, Any]) -> str:
    arguments = str((tool_call(call_message) or {}).get("arguments") or "{}")
    try:
        parsed = cast(object, json.loads(arguments))
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    return str(cast(dict[str, object], parsed).get("model") or "")


def verify_repair(
    messages: list[dict[str, Any]], run_id: str, terminal_status: str
) -> RepairOutcome:
    calls = [
        message
        for message in messages
        if (tool_call(message) or {}).get("name") == "run_claude_code_sdk"
    ]
    failures: list[str] = []
    if len(calls) != 1:
        failures.append(f"expected one SDK call, observed {len(calls)}")
    elif _sdk_model(calls[0]) != "sonnet":
        failures.append("SDK call did not use model='sonnet'")

    returns = [
        message
        for message in messages
        if message.get("message_type") == "tool_return_message"
        and message.get("name") == "run_claude_code_sdk"
    ]
    if not returns:
        failures.append("SDK tool never returned")
    else:
        returned = message_text(returns[-1]).strip()
        if returns[-1].get("is_err") or returned.upper().startswith("ERROR"):
            failures.append(f"SDK tool failed: {returned}")
        elif "SDK_REPAIR_RESULT: PASSED" not in returned:
            marker = (
                "SDK_REPAIR_RESULT: FAILED"
                if "SDK_REPAIR_RESULT: FAILED" in returned
                else "missing"
            )
            failures.append(f"SDK's final repair marker was {marker}")

    if run_id:
        if terminal_status != "complete":
            failures.append(
                f"SDK executor finished with {terminal_status or 'unknown status'}"
            )
    elif returns and not failures:
        failures.append("SDK executor run was not observable in the activity feed")

    assistants = [
        message_text(message)
        for message in messages
        if message.get("message_type") == "assistant_message"
    ]
    final = assistants[-1] if assistants else ""
    if "REPAIR_RESULT: PASSED" not in final:
        marker = (
            "REPAIR_RESULT: FAILED"
            if "REPAIR_RESULT: FAILED" in final
            else "missing"
        )
        failures.append(f"Mazda's final repair marker was {marker}")
    detail = (
        "; ".join(failures)
        if failures
        else "SDK repair and focused verification passed"
    )
    return RepairOutcome(not failures, detail, run_id)
