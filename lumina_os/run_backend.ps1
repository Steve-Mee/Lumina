# Start FastAPI backend from lumina_os with repo-root config and lumina_core on PYTHONPATH.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$env:PYTHONPATH = $RepoRoot
$env:LUMINA_CONFIG = Join-Path $RepoRoot "config.yaml"
if ([string]::IsNullOrWhiteSpace($env:LUMINA_JWT_SECRET_KEY)) {
    $env:LUMINA_JWT_SECRET_KEY = "LUMINA_LOCAL_DEVELOPMENT_JWT_SECRET_KEY_32"
}

$envFile = Join-Path $PSScriptRoot ".env"
if ((Test-Path $envFile) -and [string]::IsNullOrWhiteSpace($env:LUMINA_BACKEND_PORT)) {
    Get-Content $envFile -ErrorAction SilentlyContinue | ForEach-Object {
        $t = $_.Trim()
        if ($t -match '^(?!#)LUMINA_BACKEND_PORT\s*=\s*(\d+)\s*$') {
            $env:LUMINA_BACKEND_PORT = $Matches[1]
        }
    }
}

$Port = 8000
if (-not [string]::IsNullOrWhiteSpace($env:LUMINA_BACKEND_PORT)) {
    $Port = [int]$env:LUMINA_BACKEND_PORT
}

# Fail fast with a clear message if the port is already in use (typical: earlier uvicorn still running).
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -eq "127.0.0.1" -or $_.LocalAddress -eq "0.0.0.0" } |
    Select-Object -First 1
if ($listener) {
    $pidListen = $listener.OwningProcess
    Write-Host ""
    Write-Host "Poort $Port is al in gebruik (PID $pidListen). Een eerdere uvicorn draait waarschijnlijk nog." -ForegroundColor Yellow
    Write-Host "Stop het met: Stop-Process -Id $pidListen -Force" -ForegroundColor Yellow
    Write-Host 'Of kies een andere poort: $env:LUMINA_BACKEND_PORT=8001; .\run_backend.ps1' -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Set-Location $PSScriptRoot
python -m uvicorn backend.app:app --host 127.0.0.1 --port $Port @args
