"""Repairing the HP DeskJet's Windows print queue, and asking the printer itself.

Two separate sources of truth live here, and keeping them apart is the whole
point of the module. Windows' `PrinterStatus` says only whether the *spooler*
is happy; the printer's own LEDM web service says whether the *hardware* is.
Trusting the first alone is what once reported "Printer fixed." to an operator
standing in front of a DeskJet that had been out of paper the entire time.

The repair reaches Windows through a WSL interop socket, which the caller
injects: server.py owns the lookup, and a test that replaces it must be
honoured on the very next call.
"""

import json
import os
import subprocess
import urllib.request
from xml.etree import ElementTree

from hardware.wsl_interop import WINDOWS_POWERSHELL

# The scanner dialogs also expose a repair for the HP DeskJet's Windows print
# queue. Its old link-local IPv6 port becomes stale after printer/router
# restarts; the printer itself remains reachable on this IPv4 RAW port.
DESKJET_PRINTER_NAME = 'HP063E28 (HP DeskJet 4100 series)'
DESKJET_PRINTER_IP = '10.0.0.243'
DESKJET_PRINTER_PORT = 'IP_10.0.0.243'
WINDOWS_POWERSHELL = (
    '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')

# Windows' own PrinterStatus is NOT evidence that the printer works. This queue's
# RAW port has SNMP turned off, so the spooler never asks the hardware anything
# and reports "Normal" while the DeskJet sits there out of paper or jammed. That
# is exactly how "Printer fixed." got shown for a printer that could not print
# (2026-07-22: the device was reporting trayEmpty the whole time). The printer's
# own LEDM web service is the honest source of device state, and WSL can reach it
# directly over the LAN — no Windows interop needed.
DESKJET_STATUS_URL = f'http://{DESKJET_PRINTER_IP}/DevMgmt/ProductStatusDyn.xml'
# This button lives on the *scanner* dialogs, so device conditions are split by
# what they actually stop. Paper and ink stop printing only — the scanner glass
# does not care that the tray is empty, and failing the repair over an empty tray
# would be just as misleading as the false "Printer fixed." it replaced.
DESKJET_BLOCKING_STATUS = {
    # Mechanical/power states that take the whole device — scanner included — down.
    # An open ink door is the known cause of a Freezer scan wedged at "busy"
    # (see the scanner gotchas in dashboard/CLAUDE.md).
    'dooropen': 'A door or cover is open on the printer. Close it, then try again.',
    'coveropen': 'A door or cover is open on the printer. Close it, then try again.',
    'jamincorrectpage': 'There is a paper jam. Clear the jammed paper, then try again.',
    'jaminprinter': 'There is a paper jam. Clear the jammed paper, then try again.',
    'mediajam': 'There is a paper jam. Clear the jammed paper, then try again.',
    'scannererror': 'The scanner reported a hardware error. Power-cycle the printer, then try again.',
    'scanprocessingerror': 'The scanner reported a hardware error. Power-cycle the printer, then try again.',
    'shuttingdown': 'The printer is shutting down. Turn it back on, then try again.',
    'poweringdown': 'The printer is shutting down. Turn it back on, then try again.',
    'offline': 'The printer is offline. Turn it on and reconnect it to Wi-Fi, then try again.',
}
# Print-only conditions. Worth surfacing so nobody wonders why a print job never
# came out, but they never fail the repair — scanning works fine without paper.
DESKJET_PRINT_ONLY_STATUS = {
    'trayempty': 'it is out of paper (printing only — scanning works without paper)',
    'outofpaper': 'it is out of paper (printing only — scanning works without paper)',
    'inputtrayempty': 'it is out of paper (printing only — scanning works without paper)',
    'cartridgemissing': 'an ink cartridge is missing (printing only)',
    'inkempty': 'an ink cartridge is empty (printing only)',
    'suppliesempty': 'an ink cartridge is empty (printing only)',
}


def _xml_localname(tag):
    """Strip the `{namespace}` prefix ElementTree keeps on every tag."""
    return tag.rsplit('}', 1)[-1]


def read_deskjet_device_status(opener=urllib.request.urlopen):
    """Ask the DeskJet itself what state it is in.

    Returns `{'reachable', 'categories', 'blocker', 'note'}` — `blocker` is a
    condition that stops the device outright (scanning included), `note` is a
    print-only condition worth mentioning but never worth failing over.
    `opener` is injected so tests never touch the LAN. An unreachable or
    unparseable device is reported as `reachable: False` with no blocker — the
    port repair is still worth reporting, we just can't vouch for the hardware.
    """
    unknown = {'reachable': False, 'categories': [], 'blocker': None, 'note': None}
    try:
        with opener(DESKJET_STATUS_URL, timeout=8) as resp:
            payload = resp.read()
    except Exception:  # noqa: BLE001 — any failure here is just "can't tell"
        return unknown
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return unknown

    categories = [
        (node.text or '').strip()
        for node in root.iter()
        if _xml_localname(node.tag) == 'StatusCategory' and node.text
    ]
    blocker = None
    note = None
    for category in categories:
        key = category.lower()
        if blocker is None:
            blocker = DESKJET_BLOCKING_STATUS.get(key)
        if note is None:
            note = DESKJET_PRINT_ONLY_STATUS.get(key)
    return {
        'reachable': True,
        'categories': categories,
        'blocker': blocker,
        'note': note,
    }


def fix_deskjet_printer(interop_socket, runner=subprocess.run,
                        device_status=None):
    """Repair the DeskJet queue through Windows PowerShell.

    This is the same safe repair as the Desktop helper: verify the printer's
    RAW service, create its IPv4 port if needed, bind the existing HP queue to
    that port, and refresh the spooler. Never installs/removes a driver or
    deletes queued jobs.

    The queue repair alone is not enough to claim success: it only proves
    Windows can *talk* to the printer. Before reporting "fixed" we ask the
    printer itself (`device_status`) whether anything on the hardware is
    blocking, so a jammed or open DeskJet is named instead of hidden behind
    Windows' permanently-"Normal" PrinterStatus. Paper and ink are reported as
    a note, never a failure — this button sits on the scanner dialogs.

    `interop_socket` is a callable, not a socket path: it is consulted at the
    moment of the repair, so a caller (or a test) that swaps the lookup is
    honoured without this module knowing where the socket comes from.
    """
    check_device = device_status or read_deskjet_device_status
    interop = interop_socket()
    if not interop:
        # No Windows access, but the printer is on the LAN — a real blocker is
        # still worth naming, and is far more actionable than "open a WSL window".
        blocker = check_device().get('blocker')
        if blocker:
            return {'ok': False, 'text': blocker}
        return {
            'ok': False,
            'text': ('Printer repair needs Windows access. Open a WSL window '
                     'and try Fix Scanner again.'),
        }

    script = f"""
$ErrorActionPreference = 'Stop'
$printerName = '{DESKJET_PRINTER_NAME}'
$printerIp = '{DESKJET_PRINTER_IP}'
$portName = '{DESKJET_PRINTER_PORT}'
if (-not (Test-NetConnection -ComputerName $printerIp -Port 9100 -InformationLevel Quiet -WarningAction SilentlyContinue)) {{
    throw "The printer is not reachable at $printerIp. Make sure it is powered on and connected to Wi-Fi."
}}
if (-not (Get-Printer -Name $printerName -ErrorAction SilentlyContinue)) {{
    throw "The HP DeskJet 4100 Windows queue was not found."
}}
if (-not (Get-PrinterPort -Name $portName -ErrorAction SilentlyContinue)) {{
    Add-PrinterPort -Name $portName -PrinterHostAddress $printerIp -PortNumber 9100
}}
Set-Printer -Name $printerName -PortName $portName
try {{
    Restart-Service Spooler -Force
}} catch {{
    # The dashboard's Windows token can update this per-user queue but may not
    # be elevated enough to control the system service. The port switch is the
    # actual repair; let Windows refresh status through the new port normally.
}}
Start-Sleep -Seconds 2
$printer = Get-Printer -Name $printerName
[ordered]@{{
    ok = ([string]$printer.PrinterStatus -eq 'Normal')
    status = [string]$printer.PrinterStatus
    port = [string]$printer.PortName
}} | ConvertTo-Json -Compress
"""
    env = os.environ.copy()
    env['WSL_INTEROP'] = interop
    try:
        proc = runner(
            [WINDOWS_POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass',
             '-Command', script],
            capture_output=True, text=True, timeout=35, env=env,
        )
    except subprocess.TimeoutExpired:
        return {'ok': False, 'text': 'Printer repair timed out.'}
    except Exception as exc:  # noqa: BLE001 — surface the actionable failure
        return {'ok': False, 'text': f'Could not start printer repair: {exc}'}

    output = (proc.stdout or '').strip()
    if proc.returncode != 0:
        error = (proc.stderr or output or 'Windows printer repair failed.').strip()
        return {'ok': False, 'text': error[:500]}
    try:
        payload = json.loads(output.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {
            'ok': False,
            'text': f'Windows returned an unreadable printer status: {output[:300]}',
        }
    status = payload.get('status') or 'Unknown'
    ok = payload.get('ok') is not False
    port = payload.get('port') or DESKJET_PRINTER_PORT
    device = check_device()
    blocker = device.get('blocker')
    if ok and blocker:
        # The Windows side is healthy; the device is not. Say the thing the user
        # can act on — never "Printer fixed." over an open door or a jam.
        return {
            'ok': False,
            'text': f'Windows is connected to the printer, but {blocker[0].lower()}{blocker[1:]}',
            'status': status,
            'port': port,
            'device_status': device.get('categories'),
        }
    if ok and not device.get('reachable'):
        return {
            'ok': False,
            'text': ('The Windows queue was repaired, but the printer did not '
                     'answer when asked how it is doing. Check that it is on '
                     'and connected to Wi-Fi, then try again.'),
            'status': status,
            'port': port,
            'device_status': [],
        }
    if ok:
        note = device.get('note')
        text = 'Printer fixed — the printer reports it is ready.'
        if note:
            text = f'Printer fixed — the printer is ready to scan. Note: {note}.'
        return {
            'ok': True,
            'text': f'{text} Windows status: {status}.',
            'status': status,
            'port': port,
            'device_status': device.get('categories'),
        }
    return {
        'ok': False,
        'text': f'The port was repaired, but Windows status is still {status}.',
        'status': status,
        'port': port,
        'device_status': device.get('categories'),
    }
