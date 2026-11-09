$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Set-Location .\backend
& .\.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm run typecheck
npm run build
Write-Host "All checks passed."
