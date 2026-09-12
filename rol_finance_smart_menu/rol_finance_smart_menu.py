"""ROL Finance SmartMenu — console navigator for Mom.

Ports the class shapes from the existing SmartMenu project
(MenuItem / SmartMenuItem / Menu — a Composite: a plain MenuItem runs an
action, a SmartMenuItem instead recurses into a nested Menu) so this tool
looks and behaves like every other SmartMenu Mom might use, rather than being
a one-off script with its own conventions.

Two things don't fit the original architecture, so they're new here:

  * BrowserMenuItem — the original MenuItem.execute() runs `subprocess.run`
    and BLOCKS until the command exits. A URL opened in a browser never
    exits, so blocking would freeze the console until Mom closed the window.
    BrowserMenuItem opens the browser and returns immediately so the month
    menu redisplays right away (spec: "Immediately redisplay the same month
    menu ... so another selection can be made").

  * SmartMenuBrowserWindow — tracks the single Chrome process SmartMenu
    itself opened, so picking a second report closes the first SmartMenu
    window before opening the new one, without ever touching any other
    Chrome window Mom might have open. Achieved by giving this one Chrome
    process its own --user-data-dir: an OS-level guarantee that killing it
    can't reach into Mom's regular Chrome windows (a different process,
    different profile) even if Chrome would otherwise merge processes.

Month/report data is fetched live from the dashboard's own
/api/rol-finance-reports endpoint (same data the web app's month tabs use),
not hard-coded here, so a new report card added to the web app shows up in
this menu automatically.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

# The Tailscale Serve HTTPS front for the live dashboard — same URL already
# used for remote/Android access (see dashboard_deployment_topology memory).
# Change this if the dashboard ever moves to a different host.
DASHBOARD_BASE_URL = "https://desktop-2obsqmc.tailb8fc54.ts.net"

# 2025 is the only year the ROL Finance reports cover today (see
# finance/report_registry.py). Add a year here if/when a 2026 tab appears.
MONTHS = [
    ("jan-2025", "January"),
    ("feb-2025", "February"),
    ("mar-2025", "March"),
    ("apr-2025", "April"),
    ("may-2025", "May"),
    ("jun-2025", "June"),
    ("jul-2025", "July"),
    ("aug-2025", "August"),
    ("sep-2025", "September"),
    ("oct-2025", "October"),
    ("nov-2025", "November"),
    ("dec-2025", "December"),
]

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
    ),
]


def _find_chrome() -> str | None:
    for candidate in CHROME_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


class MenuItem:
    """A leaf: a title plus an action to run when selected."""

    def __init__(self, title):
        self.title = title

    def execute(self):
        raise NotImplementedError


class SmartMenuItem(MenuItem):
    """Composite: recurses into a nested Menu instead of running an action."""

    def __init__(self, title, build_sub_menu):
        super().__init__(title)
        # A callable, not a fixed Menu, because the month menu's contents
        # (which reports exist, the Receipt Only count) can change between
        # visits and must be re-fetched every time this item is selected.
        self._build_sub_menu = build_sub_menu

    def execute(self):
        self._build_sub_menu().display_and_select()


class SmartMenuBrowserWindow:
    """Tracks the one Chrome window SmartMenu has open, so the next report
    selection closes it before opening the next one."""

    def __init__(self, chrome_path):
        self._chrome_path = chrome_path
        self._profile_dir = os.path.join(
            tempfile.gettempdir(), "rol_finance_smart_menu_chrome_profile"
        )
        self._process = None

    def open(self, url):
        self._close_previous()
        self._process = subprocess.Popen(
            [
                self._chrome_path,
                f"--app={url}",
                f"--user-data-dir={self._profile_dir}",
                "--new-window",
            ]
        )

    def _close_previous(self):
        if self._process is None:
            return
        if self._process.poll() is None:  # still running
            try:
                self._process.terminate()
            except OSError:
                pass
        self._process = None


class BrowserMenuItem(MenuItem):
    """Opens a report URL in the tracked SmartMenu browser window and
    returns immediately (does not block on the browser process)."""

    def __init__(self, title, url, browser_window):
        super().__init__(title)
        self._url = url
        self._browser_window = browser_window

    def execute(self):
        print(f"Opening: {self.title} ...")
        try:
            self._browser_window.open(self._url)
        except OSError as exc:
            print(f"Could not open the browser: {exc}")


class Menu:
    """Numbered menu; 'x' returns to the caller."""

    def __init__(self, header_lines, items, exit_label="x. Go Back"):
        self._header_lines = header_lines
        self._items = items
        self._exit_label = exit_label

    def display_and_select(self):
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print()
            for line in self._header_lines:
                print(line)
            print()
            for index, item in enumerate(self._items, start=1):
                print(f"{index}. {item.title}")
            print(self._exit_label)

            choice = input("\nSelect an option: ").strip().lower()
            if choice == "x":
                return
            if choice.isdigit() and 1 <= int(choice) <= len(self._items):
                self._items[int(choice) - 1].execute()
            else:
                print("Invalid selection. Please try again.")


def _fetch_month_reports(month_key):
    """GET /api/rol-finance-reports?month=<key> — same data the dashboard's
    own month tabs render from. Returns [] (with a printed reason) on any
    network problem rather than raising, so a flaky Tailscale link degrades
    to 'no reports right now', not a crash."""
    url = f"{DASHBOARD_BASE_URL}/api/rol-finance-reports?month={month_key}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"\nCouldn't reach the ROL Finance dashboard: {exc}")
        return []


def _build_month_menu(month_key, month_label, browser_window):
    reports = _fetch_month_reports(month_key)
    items = []
    for entry in reports:
        if not entry.get("exists"):
            continue  # not ready yet — don't offer a link that won't load
        label = entry["label"]
        if entry.get("receipt_count") is not None:
            label = f"{label} ({entry['receipt_count']} Records)"
        # Mom only cares about the Verified Transactions table — she opens
        # report.html directly, outside the dashboard's own iframe, so the
        # server's ?verified=1 handling is what hides the other sections
        # for her (see server._report_html_with_current_picker).
        sep = "&" if "?" in entry["url"] else "?"
        url = f'{DASHBOARD_BASE_URL}{entry["url"]}{sep}verified=1'
        items.append(BrowserMenuItem(label, url, browser_window))
    header = [f"ROL Finance System:", "", month_label, "", "Select the Bank Account:"]
    if not items:
        header = [
            "ROL Finance System:",
            "",
            month_label,
            "",
            "No reports are ready for this month yet.",
        ]
    return Menu(header, items)


def _build_main_menu(browser_window):
    items = [
        SmartMenuItem(
            label,
            lambda key=key, label=label: _build_month_menu(key, f"{label} 2025", browser_window),
        )
        for key, label in MONTHS
    ]
    return Menu(
        ["ROL Finance System:", "", "2025", "", "Select the month:"],
        items,
        exit_label="x. Exit",
    )


def main():
    chrome_path = _find_chrome()
    if not chrome_path:
        print(
            "Could not find Chrome. Please install Google Chrome, or edit "
            "CHROME_CANDIDATES at the top of this file with the correct path."
        )
        input("\nPress Enter to close...")
        sys.exit(1)

    browser_window = SmartMenuBrowserWindow(chrome_path)
    _build_main_menu(browser_window).display_and_select()


if __name__ == "__main__":
    main()
