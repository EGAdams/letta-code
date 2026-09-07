"""Connect Playwright to a Chromium process that survives test disconnect."""

from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Playwright


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _browser_executable(playwright: Playwright, explicit: str | None) -> str:
    if explicit:
        return explicit
    names = (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    )
    for name in names:
        if found := shutil.which(name):
            return found
    return playwright.chromium.executable_path


def launch_detached_browser(
    playwright: Playwright, executable: str | None, headless: bool
) -> tuple[subprocess.Popen[bytes], str, Browser]:
    """Launch outside Playwright so stopping Playwright leaves Chromium open."""
    port = _free_port()
    profile = tempfile.mkdtemp(prefix="mazda-scanner-browser-")
    args = [
        _browser_executable(playwright, executable),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]
    if headless:
        args.insert(1, "--headless=new")
    process = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    endpoint = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"{endpoint}/json/version", timeout=0.2):
                browser = playwright.chromium.connect_over_cdp(endpoint)
                return process, profile, browser
        except (OSError, urllib.error.URLError):
            if process.poll() is not None:
                shutil.rmtree(profile, ignore_errors=True)
                raise RuntimeError(
                    f"Chromium exited during startup ({process.returncode}). "
                    "Run `.venv/bin/playwright install --with-deps chromium`."
                )
            time.sleep(0.1)
    process.terminate()
    shutil.rmtree(profile, ignore_errors=True)
    raise RuntimeError("Chromium's debugging endpoint did not start")
