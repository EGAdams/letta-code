#!/usr/bin/env bash
# Freezer Scanner = HP063E28 (HP DeskJet 4100 series), the NON-default device that
# is notorious for "WIA device is busy" until power-cycled. Selects it BY NAME via
# the shared scan_device.ps1. Output: scan_freezer.jpg (JPEG, ~1MB vs 26MB BMP).
cd "$(dirname "$0")" || exit 1
rm -f scan_freezer.jpg scan_freezer.png
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -ExecutionPolicy Bypass \
  -File ./scan_device.ps1 -NameLike HP063E28 -OutFile scan_freezer.jpg
