# Parameterized WIA scan — selects the target scanner BY NAME (not "first device
# found"), so it always drives the intended device even when WIA enumeration order
# shifts (the busy Freezer often enumerates first). Emits machine-readable markers
# the dashboard classifies: SCANNER_OFFLINE (exit 5), SCANNER_BUSY (exit 6),
# "Saved: <path>" (exit 0).
param(
    [string]$NameLike = "",
    [string]$OutFile = "scan.jpg",
    [int]$JpegQuality = 85
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
$wia = New-Object -ComObject WIA.DeviceManager

$infos = @($wia.DeviceInfos | Where-Object { $_.Type -eq 1 })
if ($NameLike -ne "") {
    $infos = @($infos | Where-Object {
        $n = $null
        try { $n = $_.Properties.Item("Name").Value } catch {}
        $n -like ("*" + $NameLike + "*")
    })
}
$deviceInfo = $infos | Select-Object -First 1
if (-not $deviceInfo) {
    Write-Output "SCANNER_OFFLINE"
    Write-Output ("Scanner not found matching '" + $NameLike + "'")
    exit 5
}

try {
    $device = $deviceInfo.Connect()
    $item = $device.Items.Item(1)
    try {
        $item.Properties.Item("6147").Value = 300
        $item.Properties.Item("6148").Value = 300
    } catch {}
    # Transfer as BMP (fastest, no encode overhead on the scanner side).
    $image = $item.Transfer("{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}")
} catch {
    if ($_.Exception.Message -match "busy") { Write-Output "SCANNER_BUSY" }
    Write-Output ("Scan failed: " + $_.Exception.Message)
    exit 6
}

try { $pwdPath = $PWD.ProviderPath } catch { $pwdPath = $PWD.Path }
$output = Join-Path -Path $pwdPath -ChildPath $OutFile
$dir = [System.IO.Path]::GetDirectoryName($output)
if ($dir -and -not (Test-Path $dir)) {
    try { New-Item -ItemType Directory -Path $dir -Force | Out-Null } catch {}
}

# Save the raw WIA image to a temp file, then re-encode as JPEG via
# System.Drawing (BMP→JPEG shrinks a 300dpi flatbed scan from ~26MB to ~1MB).
$tmpFile = $output + ".tmp"
$saved = $false
try {
    $image.SaveFile([string]$tmpFile)
    $saved = $true
} catch {
    Write-Output ("WIA SaveFile failed: " + $_.Exception.Message)
}
if (-not $saved) {
    try {
        [Byte[]]$bytes = $image.FileData.BinaryData
        [System.IO.File]::WriteAllBytes($tmpFile, $bytes)
        $saved = $true
    } catch {
        Write-Output ("Fallback write failed: " + $_.Exception.Message)
        exit 4
    }
}

try {
    $bmp = [System.Drawing.Image]::FromFile($tmpFile)
    $jpegCodec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() |
        Where-Object { $_.MimeType -eq "image/jpeg" }
    $params = New-Object System.Drawing.Imaging.EncoderParameters(1)
    $params.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter(
        [System.Drawing.Imaging.Encoder]::Quality, [long]$JpegQuality)
    $bmp.Save([string]$output, $jpegCodec, $params)
    $bmp.Dispose()
    Remove-Item -Path $tmpFile -Force -ErrorAction SilentlyContinue
} catch {
    # JPEG re-encode failed — fall back to the raw file so the scan isn't lost.
    Write-Output ("JPEG encode failed, keeping raw: " + $_.Exception.Message)
    Move-Item -Path $tmpFile -Destination $output -Force
}
Write-Output ("Saved: " + $output)
exit 0
