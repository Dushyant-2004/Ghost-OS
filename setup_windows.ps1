$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\backend\.venv\Scripts\python.exe")) {
    python -m venv .\backend\.venv
}
& .\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
& .\backend\.venv\Scripts\python.exe -m playwright install chromium
Set-Location .\frontend
npm install
Write-Host "GhostOS dependencies and Chromium are ready."
