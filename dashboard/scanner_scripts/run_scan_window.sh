#!/usr/bin/env bash
# Window Scanner = HPI297BEA (HP OfficeJet 8120e series). Selects it BY NAME via
# the shared scan_device.ps1 (not "first device"), so it is unaffected by the
# Freezer enumerating first. Output: scan.jpg (JPEG, ~1MB vs 26MB BMP).
cd "$(dirname "$0")" || exit 1
rm -f scan.jpg scan.png
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -ExecutionPolicy Bypass \
  -File ./scan_device.ps1 -NameLike HPI297BEA -OutFile scan.jpg
