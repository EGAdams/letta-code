#!/usr/bin/env bash
# Window Scanner = HP OfficeJet 8120e. Drive its native eSCL endpoint through
# sane-airscan so stale Windows WIA/WSD state cannot block the dashboard.
cd "$(dirname "$0")" || exit 1
rm -f window_scan.jpg window_scan.png
exec ./scan_airscan.sh "airscan:e0:Window Scanner" window_scan.jpg
