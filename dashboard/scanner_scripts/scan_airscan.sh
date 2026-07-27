#!/usr/bin/env bash
# Scan one statically configured eSCL device through sane-airscan. This avoids
# Windows WIA/WSD entirely; both HP scanners remain usable even when Windows
# leaves their old WSD records disconnected with PnP Problem 45.
set -u

device=${1:?airscan device name required}
output=${2:?output filename required}

rm -f "$output"
if ! command -v scanimage >/dev/null 2>&1; then
  echo "SCANNER_OFFLINE"
  echo "Native AirScan backend is not installed."
  exit 5
fi

scan_log=$(
  timeout --foreground 85s scanimage -d "$device" \
    --source Flatbed \
    --resolution 300 \
    --mode Color \
    --format=jpeg \
    --output-file="$output" \
    --progress 2>&1
)
result=$?
printf '%s\n' "$scan_log"

if [[ $result -eq 0 && -s "$output" ]]; then
  echo "Saved: $PWD/$output"
  exit 0
fi

rm -f "$output"
if [[ ${scan_log,,} == *busy* ]]; then
  echo "SCANNER_BUSY"
  exit 6
fi
if [[ ${scan_log,,} == *"not found"* || ${scan_log,,} == *"i/o error"* ]]; then
  echo "SCANNER_OFFLINE"
  exit 5
fi
exit "${result:-1}"
