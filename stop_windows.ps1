$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Get-ProcessTreeIds([int]$RootId) {
    $ids = New-Object System.Collections.Generic.List[int]
    $pending = New-Object System.Collections.Generic.Queue[int]
    $pending.Enqueue($RootId)
    while ($pending.Count -gt 0) {
        $current = $pending.Dequeue()
        if ($ids.Contains($current)) { continue }
        $ids.Add($current)
        Get-CimInstance Win32_Process -Filter "ParentProcessId = $current" |
            ForEach-Object { $pending.Enqueue([int]$_.ProcessId) }
    }
    return $ids
}

$pidFile = Join-Path $PSScriptRoot ".ghostos-processes"
if (-not (Test-Path $pidFile)) {
    Write-Host "No GhostOS process file found; nothing to stop."
    exit 0
}

$processIds = @(
    Get-Content $pidFile |
        Where-Object { $_ -match "^\d+$" } |
        ForEach-Object { Get-ProcessTreeIds ([int]$_) }
) | Sort-Object -Descending -Unique

foreach ($processId in $processIds) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -ne $process) {
        Stop-Process -Id $processId -Force
        Write-Host "Stopped process $processId ($($process.ProcessName))."
    }
}

Remove-Item $pidFile -Force
Write-Host "GhostOS processes stopped."
