#!/usr/bin/env bash
set -euo pipefail

echo "[cleanup] apt cache"
sudo apt clean

echo "[cleanup] journal (last 1 day)"
sudo journalctl --vacuum-time=1d || true

echo "[cleanup] user cache"
rm -rf "${HOME}/.cache/"* || true

echo "[cleanup] fstrim (recommended)"
sudo fstrim -av || true

echo "[cleanup] done"