# ROL Finance SmartMenu

A console menu for Mom: pick a month, pick a bank account/report, it opens in
Chrome.

Two versions, same behavior:
- `rol_finance_smart_menu.ps1` — **the one deployed to Mom's PC.** Pure
  PowerShell (built into Windows), nothing to install. Her machine has no
  real Python (`python.exe` there is just the Microsoft Store stub), so this
  is the version that actually runs there.
- `rol_finance_smart_menu.py` — reference/maintained version, ported 1:1 from
  the original SmartMenu class design. Keep both in sync if you change the
  menu logic.

## Deploy to Mom's PC (Windows desktop)

1. Copy this whole folder to her Desktop (`/mnt/c/Users/rbarn/OneDrive/Desktop/`
   via the rosemary46-24 WSL node, `ssh adamsl@100.72.34.38` — her Desktop is
   OneDrive-redirected, not the plain `Users\rbarn\Desktop` path).
2. Requires Google Chrome (already installed on her machine as of this
   writing).
3. Double-click `Launch ROL Finance SmartMenu.bat` — it runs the `.ps1` via
   `powershell -ExecutionPolicy Bypass`, so no execution-policy prompt.

## How it works

- Fetches the live report list from the dashboard's own
  `/api/rol-finance-reports?month=<key>` endpoint — the same data the web
  app's month tabs use — so a new report card shows up here automatically.
- Only reports/documents that are actually ready (`exists: true`) are listed.
- Opens reports in a dedicated Chrome window (`--app` mode, its own
  `--user-data-dir`), separate from Mom's normal Chrome profile. Picking
  another report closes that one SmartMenu window first — it never touches
  any other Chrome window she has open.
- `DASHBOARD_BASE_URL` at the top of `rol_finance_smart_menu.py` points at
  the dashboard's Tailscale HTTPS front. If that URL ever changes, update it
  there.

## If Chrome isn't found

Edit `CHROME_CANDIDATES` at the top of `rol_finance_smart_menu.py` and add
the correct path to `chrome.exe`.
