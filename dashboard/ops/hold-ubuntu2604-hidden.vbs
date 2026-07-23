' Launches hold-ubuntu2604.ps1 with no visible window.
' wscript.exe is a GUI host, so nothing flashes when the task starts; the hidden console it
' creates for PowerShell is inherited by wsl.exe, so the holder is invisible too.
' Window style 0 = hidden, bWaitOnReturn = False so the task completes immediately.
CreateObject("WScript.Shell").Run _
  "powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File ""C:\Users\NewUser\hold-ubuntu2604.ps1""", _
  0, False
