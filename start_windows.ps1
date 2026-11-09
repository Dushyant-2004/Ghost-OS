$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$backend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\backend'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload" -PassThru
$frontend = Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\frontend'; npm run dev" -PassThru
Set-Content .ghostos-processes "$($backend.Id)`n$($frontend.Id)"
Write-Host "Backend and frontend started."
