#!/usr/bin/env python3
"""Operator-run Playwright test for Last Window/Freezer Scan.

This is intentionally not collected by pytest: it starts real hardware, may
ask Mazda to start a paid Claude SDK repair, and leaves its Chromium window
running after this process disconnects.

An approved repair stays in the foreground, streams Mazda and SDK telemetry,
and exits nonzero unless the SDK run and its focused verification both pass.

Setup once:
  .venv/bin/pip install -r requirements-dev.txt
  .venv/bin/playwright install --with-deps chromium

Run one physical scanner at a time:
  .venv/bin/python tests/last_scanner_operations_browser_test.py window
  .venv/bin/python tests/last_scanner_operations_browser_test.py freezer
"""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from detached_playwright_browser import launch_detached_browser
from scanner_repair_dispatch import build_repair_instruction
from scanner_repair_workflow import run_foreground_repair

if TYPE_CHECKING:
    from playwright.sync_api import Frame, Page

DEFAULT_DASHBOARD = "http://100.102.209.100:8765"
DEFAULT_LETTA = "http://100.80.49.10:8283"
GREEN_COLORS = {"rgb(0, 128, 0)", "rgba(0, 128, 0, 1)"}


@dataclass(frozen=True)
class ReportState:
    kind: str
    status: str
    conversation_id: str = ""
    document_path: str = ""


def _dismiss_unrelated_dialogs(page: Page) -> None:
    page.wait_for_timeout(4_000)
    review = page.locator("#statement-review-dialog")
    if review.is_visible():
        review.get_by_role("button", name="Leave for later", exact=True).click()
    for button in page.get_by_role("button").all():
        label = (button.inner_text() or "").strip()
        if label in {"Close Dialog", "Close this Dialog", "Close Set Category dialog"}:
            button.click()


def _report_frame(page: Page, scanner: str, timeout: float = 20) -> Frame:
    deadline = time.monotonic() + timeout
    marker = f"/scanner_report.html?scanner={scanner}"
    while time.monotonic() < deadline:
        for frame in page.frames:
            if marker in frame.url:
                return frame
        page.wait_for_timeout(100)
    raise AssertionError(f"{scanner.title()} Scanner report iframe did not load")


def _verify_automatic(page: Page, frame: Frame) -> None:
    api = cast(
        dict[str, object],
        page.evaluate("async () => (await fetch('/api/mazda-mode')).json()"),
    )
    assert api.get("automatic") is True, f"Mazda API is not automatic: {api}"
    toggle = frame.locator('input[data-field="mazdaMode"]')
    toggle.wait_for(state="attached", timeout=20_000)
    label = frame.locator(".mazda-mode-label")
    assert label.inner_text().strip() == "Mazda Automatic"
    assert toggle.is_checked(), "Mazda Automatic toggle is not checked"
    color = cast(
        str,
        frame.locator(".mazda-mode-track").evaluate(
            "element => getComputedStyle(element).backgroundColor"
        ),
    )
    assert color in GREEN_COLORS, f"Mazda Automatic toggle is not green ({color})"


def _fingerprint(frame: Frame) -> float:
    return float(cast(float, frame.evaluate("performance.timeOrigin")))


def _wait_for_scan(
    page: Page, section: str, old_fingerprint: float, timeout: float
) -> Frame:
    state = page.locator(f"#{section} .scanner-report-controls .scanner-state")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        text = (state.inner_text() or "").strip()
        if text == "Scan Finished":
            frame = _report_frame(page, section.removeprefix("scanners-last-"))
            try:
                if _fingerprint(frame) != old_fingerprint:
                    return frame
            except Exception:
                pass
        if (
            text.startswith("Scan failed:")
            or text.startswith("The previous document from this scanner")
            or text
            in {
                "Restart the Scanner Please",
                "Previous scan is still being verified.",
            }
        ):
            raise AssertionError(text)
        page.wait_for_timeout(200)
    raise TimeoutError(f"Scan did not finish within {timeout:g} seconds")


def _read_report_state(frame: Frame) -> ReportState:
    banner = frame.locator("p.status-banner")
    banner.wait_for(state="visible", timeout=20_000)
    status = (banner.inner_text() or "").strip()
    root = frame.locator("#manual-entry-root")
    conversation = root.get_attribute("data-conversation-id") if root.count() else ""
    document = root.get_attribute("data-image-path") if root.count() else ""
    if frame.locator(".mazda-working").is_visible():
        return ReportState("working", status, conversation or "", document or "")
    if "status-bad" in (banner.get_attribute("class") or "").split():
        return ReportState("failure", status, conversation or "", document or "")
    return ReportState("finished", status, conversation or "", document or "")


def _ask_repair(page: Page, failure: str) -> bool:
    page.evaluate(
        """failure => {
          window.__mazdaRepairChoice = null;
          const box = document.createElement('div'); box.id = 'mazda-repair-question';
          box.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:#0008;display:grid;place-items:center';
          const panel = document.createElement('div');
          panel.style.cssText = 'width:min(620px,90vw);background:#c0c0c0;border:3px outset #fff;padding:20px;font:18px Arial';
          const question = document.createElement('p');
          question.textContent = 'Have Mazda run the claude code SDK tool?';
          const detail = document.createElement('pre'); detail.textContent = failure;
          detail.style.cssText = 'white-space:pre-wrap;max-height:35vh;overflow:auto;background:#fff;padding:10px';
          for (const answer of ['YES', 'NO']) { const b = document.createElement('button');
            b.textContent = answer; b.style.cssText = 'margin-right:16px;padding:8px 28px';
            b.onclick = () => { window.__mazdaRepairChoice = answer; box.remove(); }; panel.appendChild(b); }
          panel.prepend(question, detail); box.appendChild(panel); document.body.appendChild(box);
        }""",
        failure,
    )
    while True:
        choice = cast(str | None, page.evaluate("window.__mazdaRepairChoice"))
        if choice:
            return choice == "YES"
        page.wait_for_timeout(200)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scanner", choices=("window", "freezer"))
    parser.add_argument("--dashboard-url", default=os.getenv("MAZDA_DASHBOARD_URL", DEFAULT_DASHBOARD))
    parser.add_argument("--letta-url", default=os.getenv("LETTA_BASE_URL", DEFAULT_LETTA))
    parser.add_argument("--scan-timeout", type=float, default=120)
    parser.add_argument("--mazda-timeout", type=float, default=900)
    parser.add_argument("--browser-executable")
    parser.add_argument("--headless", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Install browser-test dependencies: .venv/bin/pip install -r requirements-dev.txt") from exc
    manager = sync_playwright().start()
    browser_process = None
    try:
        browser_process, profile, browser = launch_detached_browser(
            manager, args.browser_executable, args.headless
        )
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(f"{args.dashboard_url.rstrip('/')}/", wait_until="domcontentloaded")
        _dismiss_unrelated_dialogs(page)
        page.get_by_role("button", name="ROL Finance", exact=True).click()
        page.get_by_role("button", name="Scanners", exact=True).click()
        tab_name = f"Last {args.scanner.title()} Scan"
        page.get_by_role("button", name=tab_name, exact=True).click()
        section = f"scanners-last-{args.scanner}"
        frame = _report_frame(page, args.scanner)
        _verify_automatic(page, frame)
        old_fingerprint = _fingerprint(frame)
        page.locator(f"#{section} .scanner-report-start").click()
        frame = _wait_for_scan(page, section, old_fingerprint, args.scan_timeout)
        outcome = _read_report_state(frame)
        print(f"{tab_name}: {outcome.status}")
        exit_code = 0
        if outcome.kind == "working":
            print("Mazda Working is visible; test stopped with Chromium left open.")
        elif outcome.kind == "failure" and _ask_repair(page, outcome.status):
            instruction = build_repair_instruction(
                args.scanner, outcome.status, outcome.document_path
            )
            repair = run_foreground_repair(
                args.dashboard_url,
                args.letta_url,
                outcome.conversation_id,
                instruction,
                args.mazda_timeout,
            )
            exit_code = 0 if repair.passed else 1
        else:
            print("Test stopped with Chromium left open.")
        print(f"Browser PID {browser_process.pid}; profile {profile}")
        return exit_code
    finally:
        # Chromium was launched independently. Stopping Playwright disconnects
        # automation but intentionally leaves the operator's window untouched.
        manager.stop()


if __name__ == "__main__":
    raise SystemExit(main())
