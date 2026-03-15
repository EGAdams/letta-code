---
name: receipt-scanner-wsl
description: "Runs the receipt scanner from WSL using Windows PowerShell and fixes common script/path issues. Use when the user asks to run the receipt scanner, fix run_scan_image.sh, or troubleshoot WSL/PowerShell scanner failures."
---

# Receipt Scanner (WSL)

## When to use
- User asks to **run the receipt scanner**.
- `run_scan_image.sh` fails with `powershell.exe: command not found` or WIA/COM errors.
- `scan_image.ps1` missing or in the wrong folder.

## Key paths
- Script folder: `/home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools`
- Runner: `/home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/run_scan_image.sh`
- PowerShell script: `/home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/scan_image.ps1`
- Windows PowerShell exe: `/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`

## Run (happy path)
```bash
cd /home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools
bash run_scan_image.sh
```
Expected output includes `scan.png` saved in the same folder.

## Fixes if it fails
### 1) Ensure scan_image.ps1 exists
```bash
ls -l /home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/scan_image.ps1
```
If missing, place the file in the script folder.

### 2) Ensure run_scan_image.sh uses Windows PowerShell
`run_scan_image.sh` must call the Windows PowerShell exe (not `pwsh`).

```bash
# quick check
sed -n '1,200p' /home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/run_scan_image.sh
```
It should include this line:
```
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -ExecutionPolicy Bypass -File "$SCRIPT"
```
If not, update it:
```bash
sed -i 's#pwsh#/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe#' /home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/run_scan_image.sh
sed -i 's#powershell.exe#/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe#' /home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools/run_scan_image.sh
```

### 3) Run again from the script directory
```bash
cd /home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools
bash run_scan_image.sh
```

## Common failures
- `powershell.exe: command not found` → update to Windows PowerShell path above.
- `New-Object : A parameter cannot be found that matches parameter name 'ComObject'` → you’re using Linux pwsh; switch to Windows PowerShell.
- `PowerShell script not found` → `scan_image.ps1` not in the script folder.

## Success criteria
- `scan.png` exists in `/home/adamsl/planner/nonprofit_finance_db/receipt_scanning_tools`.
