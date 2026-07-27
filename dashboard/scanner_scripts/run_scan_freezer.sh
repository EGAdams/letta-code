#!/usr/bin/env bash
# Freezer Scanner = HP DeskJet 4100. Drive its native eSCL endpoint through
# sane-airscan so stale Windows WIA/WSD state cannot block the dashboard.
cd "$(dirname "$0")" || exit 1
rm -f scan_freezer.jpg scan_freezer.png
exec ./scan_airscan.sh "airscan:e1:Freezer Scanner" scan_freezer.jpg
