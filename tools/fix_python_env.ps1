# fix_python_env.ps1 — consolidate to a single, fully-provisioned Python.
#
# Run ELEVATED (admin). Grants the interactive user Modify on C:\Python314's
# site-packages + Scripts so all pip installs land in the SYSTEM site-packages
# (visible even under `python -s` / PYTHONNOUSERSITE — the failure mode that made
# the canary report "No module named docpluck"), then (re)installs the full
# docpluck dependency set there. Verification is done by the caller afterwards.
param(
  [string]$User = "filin",
  [string]$Repo = "C:\Users\filin\Dropbox\Vibe\MetaScienceTools\docpluck",
  [string]$Py   = "C:\Python314\python.exe"
)
$ErrorActionPreference = "Continue"
$log = Join-Path $Repo "tmp\pyfix.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
"=== fix_python_env $(Get-Date -Format o) ===" | Out-File $log
"whoami (elevated): $(whoami)" | Out-File $log -Append
"target user: $User   python: $Py" | Out-File $log -Append

"`n=== grant Modify on site-packages + Scripts to $User ===" | Out-File $log -Append
icacls "C:\Python314\Lib\site-packages" /grant "${User}:(OI)(CI)M" /T 2>&1 | Out-File $log -Append
icacls "C:\Python314\Scripts"           /grant "${User}:(OI)(CI)M" /T 2>&1 | Out-File $log -Append

"`n=== upgrade pip ===" | Out-File $log -Append
& $Py -m pip install --upgrade pip 2>&1 | Out-File $log -Append

"`n=== install docpluck[all] (editable) into SYSTEM site ===" | Out-File $log -Append
Set-Location $Repo
& $Py -m pip install --upgrade -e ".[all]" 2>&1 | Out-File $log -Append

"`n=== install dev/runtime deps into SYSTEM site ===" | Out-File $log -Append
& $Py -m pip install --upgrade pytest pytest-xdist rapidfuzz reportlab "camelot-py[cv]" beautifulsoup4 lxml mammoth requests pyyaml 2>&1 | Out-File $log -Append

"DONE" | Out-File $log -Append
