"""Foreground observer for the Mazda -> Claude SDK repair workflow."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol, cast

from scanner_repair_dispatch import (
    conversation_messages,
    sdk_activity,
    send_mazda_repair,
)
from scanner_repair_reporting import (
    Emit,
    RepairOutcome,
    render_activity,
    render_message,
    response_messages,
    tool_call,
    verify_repair,
)

TERMINAL_STATUSES = {"complete", "cancelled", "timed_out", "error"}


def _stdout_emit(text: str) -> None:
    print(text, flush=True)


class RepairTelemetry(Protocol):
    def messages(self) -> list[dict[str, Any]]: ...

    def activity(self) -> dict[str, Any]: ...

    def dispatch(self, instruction: str) -> object: ...


class HttpRepairTelemetry:
    def __init__(
        self,
        dashboard_url: str,
        letta_url: str,
        conversation_id: str,
        request_timeout: float,
    ) -> None:
        self.dashboard_url = dashboard_url
        self.letta_url = letta_url
        self.conversation_id = conversation_id
        self.request_timeout = request_timeout

    def messages(self) -> list[dict[str, Any]]:
        return conversation_messages(self.letta_url, self.conversation_id)

    def activity(self) -> dict[str, Any]:
        return sdk_activity(self.dashboard_url)

    def dispatch(self, instruction: str) -> object:
        return send_mazda_repair(
            self.letta_url,
            self.conversation_id,
            instruction,
            self.request_timeout,
        )


class ForegroundRepairWorkflow:
    def __init__(
        self,
        telemetry: RepairTelemetry,
        emit: Emit | None = None,
        poll_interval: float = 1,
    ) -> None:
        self.telemetry = telemetry
        self.emit: Emit = emit or _stdout_emit
        self.poll_interval = poll_interval

    def run(self, instruction: str) -> RepairOutcome:
        try:
            baseline_messages = self.telemetry.messages()
            baseline_activity = self.telemetry.activity()
        except Exception as exc:
            self.emit(f"Repair telemetry unavailable; request not sent: {exc}")
            return RepairOutcome(False, str(exc))

        known_ids = {str(item.get("id")) for item in baseline_messages}
        baseline_seq = max(
            (int(event.get("seq", 0)) for event in baseline_activity["events"]),
            default=0,
        )
        observed: list[dict[str, Any]] = []
        activity_events: list[dict[str, Any]] = []
        rendered_seqs: set[int] = set()
        run_id = ""
        terminal_status = ""
        settled = 0

        self.emit(f"\nSending repair request to Mazda:\n{instruction}")
        self.emit("\nMazda and Claude Code SDK live activity:")
        response: object = cast(object, {})
        response_collected = False

        def observe_messages(messages: list[dict[str, Any]]) -> None:
            for message in messages:
                identity = str(message.get("id"))
                if identity in known_ids:
                    continue
                known_ids.add(identity)
                observed.append(message)
                render_message(message, self.emit)

        with ThreadPoolExecutor(max_workers=2) as pool:
            dispatch = pool.submit(self.telemetry.dispatch, instruction)
            message_fetch = pool.submit(self.telemetry.messages)
            while True:
                if message_fetch.done():
                    try:
                        observe_messages(message_fetch.result())
                    except Exception as exc:
                        self.emit(f"\nMazda activity read failed: {exc}")
                    message_fetch = pool.submit(self.telemetry.messages)

                if dispatch.done() and not response_collected:
                    response_collected = True
                    try:
                        response = dispatch.result()
                        observe_messages(response_messages(response))
                    except Exception as exc:
                        self.emit(
                            f"\nMazda repair request failed:\n"
                            f"{type(exc).__name__}: {exc}"
                        )

                try:
                    payload = self.telemetry.activity()
                    event_values = cast(list[object], payload["events"])
                    fresh: list[dict[str, Any]] = []
                    for value in event_values:
                        if not isinstance(value, dict):
                            continue
                        event = cast(dict[str, Any], value)
                        if int(event.get("seq", 0)) > baseline_seq:
                            fresh.append(event)
                    activity_events = fresh
                    saw_call = any(
                        (tool_call(message) or {}).get("name") == "run_claude_code_sdk"
                        for message in observed
                    )
                    if saw_call and not run_id:
                        started = next(
                            (
                                event
                                for event in fresh
                                if event.get("category") == "status"
                                and str(event.get("text", "")).startswith("Started ")
                            ),
                            None,
                        )
                        if started:
                            run_id = str(started.get("run_id") or "")
                    for event in activity_events:
                        seq = int(event.get("seq", 0))
                        if run_id and event.get("run_id") == run_id and seq not in rendered_seqs:
                            rendered_seqs.add(seq)
                            render_activity(event, self.emit)
                            status = str(event.get("status") or "")
                            if status in TERMINAL_STATUSES:
                                terminal_status = status
                except Exception as exc:
                    self.emit(f"\nClaude SDK activity read failed: {exc}")

                if dispatch.done() and (not run_id or terminal_status):
                    settled += 1
                    if settled >= 2:
                        break
                else:
                    settled = 0
                time.sleep(self.poll_interval)

        observe_messages(response_messages(response))

        self.emit("\nRepair request and related SDK process have stopped.")
        self.emit("Running verification...")
        outcome = verify_repair(observed, run_id, terminal_status)
        self.emit(f"\nFinal result:\n{'PASSED' if outcome.passed else 'FAILED'}")
        self.emit(outcome.detail)
        return outcome


def run_foreground_repair(
    dashboard_url: str,
    letta_url: str,
    conversation_id: str,
    instruction: str,
    timeout: float,
) -> RepairOutcome:
    telemetry = HttpRepairTelemetry(
        dashboard_url, letta_url, conversation_id, timeout
    )
    return ForegroundRepairWorkflow(telemetry).run(instruction)
