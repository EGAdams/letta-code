# ROL Finance SmartMenu — console navigator for Mom (PowerShell port).
#
# Ported from rol_finance_smart_menu.py (kept in this folder as the
# reference/maintained version) because Mom's PC has no real Python
# installed — python.exe there is just the Microsoft Store stub. PowerShell
# ships with Windows, so this needs nothing installed.
#
# Same design as the Python version:
#   - Main menu: 12 months of 2025. Month menu: live report cards fetched
#     from the dashboard's own /api/rol-finance-reports?month=<key> endpoint
#     (same data the web app's month tabs use) - not hard-coded, and only
#     reports that are actually ready (exists=true) are listed.
#   - Each report opens in its own Chrome --app window with a dedicated
#     --user-data-dir, tracked in $script:ChromeProcess. Picking another
#     report kills that ONE tracked process first - never touches any other
#     Chrome window Mom has open, because it lives in its own profile/process.
#   - Opening a report does not block, so the month menu redisplays right
#     away for another pick.

$ErrorActionPreference = 'Stop'

# Mom's readability: bump the console font the same way she would by hand —
# 5 presses of Ctrl-+ (Windows' console host steps font size on that
# shortcut). SendKeys targets whatever window has focus, which right after
# launch is this console, so no window-handle lookup is needed.
Add-Type -AssemblyName System.Windows.Forms
Start-Sleep -Milliseconds 300
for ($i = 0; $i -lt 5; $i++) {
    [System.Windows.Forms.SendKeys]::SendWait('^=')
    Start-Sleep -Milliseconds 100
}

$DashboardBaseUrl = 'https://desktop-2obsqmc.tailb8fc54.ts.net'

$Months = @(
    @{ Key = 'jan-2025'; Label = 'January' },
    @{ Key = 'feb-2025'; Label = 'February' },
    @{ Key = 'mar-2025'; Label = 'March' },
    @{ Key = 'apr-2025'; Label = 'April' },
    @{ Key = 'may-2025'; Label = 'May' },
    @{ Key = 'jun-2025'; Label = 'June' },
    @{ Key = 'jul-2025'; Label = 'July' },
    @{ Key = 'aug-2025'; Label = 'August' },
    @{ Key = 'sep-2025'; Label = 'September' },
    @{ Key = 'oct-2025'; Label = 'October' },
    @{ Key = 'nov-2025'; Label = 'November' },
    @{ Key = 'dec-2025'; Label = 'December' }
)

$ChromeCandidates = @(
    "$Env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${Env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$Env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

function Find-Chrome {
    foreach ($candidate in $ChromeCandidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $candidate
        }
    }
    return $null
}

$script:ChromeProcess = $null
$script:ChromeProfileDir = Join-Path $Env:TEMP 'rol_finance_smart_menu_chrome_profile'

function Open-ReportInBrowser {
    param([string]$Title, [string]$Url, [string]$ChromePath)

    # Close the previous SmartMenu-opened window before opening the next one.
    if ($script:ChromeProcess -and -not $script:ChromeProcess.HasExited) {
        try { $script:ChromeProcess.Kill() } catch { }
    }

    Write-Host "Opening: $Title ..."
    # Diagnostic only — never blocks opening the browser. This is what will
    # show up in a copy-pasted console transcript if a report URL is ever
    # actually broken, instead of us having to guess from a screenshot.
    try {
        $check = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
        Write-Host "  (dashboard responded: $($check.StatusCode))"
    } catch {
        Write-Host "  (dashboard check failed: $($_.Exception.Message))"
    }
    try {
        $script:ChromeProcess = Start-Process -FilePath $ChromePath -ArgumentList @(
            "--app=$Url",
            "--user-data-dir=$script:ChromeProfileDir",
            '--new-window'
        ) -PassThru
    } catch {
        Write-Host "Could not open the browser: $($_.Exception.Message)"
    }
}

function Get-MonthReports {
    param([string]$MonthKey)
    $url = "$DashboardBaseUrl/api/rol-finance-reports?month=$MonthKey"
    try {
        return Invoke-RestMethod -Uri $url -TimeoutSec 10
    } catch {
        Write-Host ''
        Write-Host "Couldn't reach the ROL Finance dashboard: $($_.Exception.Message)"
        return @()
    }
}

function Show-MonthMenu {
    param([string]$MonthKey, [string]$MonthLabel, [string]$ChromePath)

    while ($true) {
        Clear-Host
        $reports = Get-MonthReports -MonthKey $MonthKey
        $items = @($reports | Where-Object { $_.exists })

        Write-Host ''
        Write-Host 'ROL Finance System:'
        Write-Host ''
        Write-Host $MonthLabel
        Write-Host ''
        if ($items.Count -eq 0) {
            Write-Host 'No reports are ready for this month yet.'
        } else {
            Write-Host 'Select the Bank Account:'
        }
        Write-Host ''

        $labels = @()
        for ($i = 0; $i -lt $items.Count; $i++) {
            $entry = $items[$i]
            $label = $entry.label
            if ($null -ne $entry.receipt_count) {
                $label = "$label ($($entry.receipt_count) Records)"
            }
            $labels += $label
            Write-Host "$($i + 1). $label"
        }
        Write-Host 'x. Go Back'

        $choice = (Read-Host "`nSelect an option").Trim().ToLower()
        if ($choice -eq 'x') { return }
        if ($choice -match '^\d+$') {
            $n = [int]$choice
            if ($n -ge 1 -and $n -le $items.Count) {
                $entry = $items[$n - 1]
                # Mom only cares about Verified Transactions; ?verified=1 tells
                # the server to hide the other report sections for her.
                # NOTE: -like treats '?' as a single-char wildcard, so it
                # always matched here regardless of content — use a literal
                # Contains() check instead (bug found 2026-09-11: this always
                # picked '&', producing "report.html&verified=1" with no '?'
                # at all, which the server can't match -> 404).
                $sep = if ($entry.url.Contains('?')) { '&' } else { '?' }
                $url = "$DashboardBaseUrl$($entry.url)${sep}verified=1"
                Open-ReportInBrowser -Title $labels[$n - 1] -Url $url -ChromePath $ChromePath
                continue
            }
        }
        Write-Host 'Invalid selection. Please try again.'
    }
}

function Show-MainMenu {
    param([string]$ChromePath)

    while ($true) {
        Clear-Host
        Write-Host ''
        Write-Host 'ROL Finance System:'
        Write-Host ''
        Write-Host '2025'
        Write-Host ''
        Write-Host 'Select the month:'
        Write-Host ''
        for ($i = 0; $i -lt $Months.Count; $i++) {
            Write-Host "$($i + 1). $($Months[$i].Label)"
        }
        Write-Host 'x. Exit'

        $choice = (Read-Host "`nSelect an option").Trim().ToLower()
        if ($choice -eq 'x') { return }
        if ($choice -match '^\d+$') {
            $n = [int]$choice
            if ($n -ge 1 -and $n -le $Months.Count) {
                $month = $Months[$n - 1]
                Show-MonthMenu -MonthKey $month.Key -MonthLabel "$($month.Label) 2025" -ChromePath $ChromePath
                continue
            }
        }
        Write-Host 'Invalid selection. Please try again.'
    }
}

$chromePath = Find-Chrome
if (-not $chromePath) {
    Write-Host 'Could not find Chrome. Please install Google Chrome, or edit'
    Write-Host '$ChromeCandidates at the top of this file with the correct path.'
    Read-Host "`nPress Enter to close"
    exit 1
}

Show-MainMenu -ChromePath $chromePath
