# Verify BRO-v2 deploy gate before starting or resuming Birth Phase.
# Usage: .\scripts\verify-birth-deploy.ps1 [-BackendUrl "http://127.0.0.1:8000"] [-LogPath "logs\lumina_full_log.csv"]
param(
    [string]$BackendUrl = "http://127.0.0.1:8000",
    [string]$LogPath = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = Join-Path $RepoRoot "logs\lumina_full_log.csv"
}

Write-Host "Birth deploy gate: checking $BackendUrl/api/birth/status ..." -ForegroundColor Cyan

try {
    $response = Invoke-RestMethod -Uri "$BackendUrl/api/birth/status" -Method Get -TimeoutSec 15
}
catch {
    Write-Host "FAIL: Backend unreachable at $BackendUrl. Start lumina_os/run_backend.ps1" -ForegroundColor Red
    exit 1
}

$engineVersion = [string]$response.engine_version
if ($engineVersion -ne "BRO-v2") {
    Write-Host "FAIL: engine_version='$engineVersion' (expected BRO-v2). Restart backend after deploy." -ForegroundColor Red
    exit 1
}

Write-Host "OK: engine_version=BRO-v2" -ForegroundColor Green
Write-Host "  status=$($response.status) live=$($response.live) fast_path_eligible=$($response.fast_path_eligible)"

if (Test-Path $LogPath) {
    $recent = Select-String -Path $LogPath -Pattern "birth\.engine\.version=BRO-v2" |
        Select-Object -Last 1
    if ($recent) {
        Write-Host "OK: Recent log marker: $($recent.Line.Trim())" -ForegroundColor Green
    }
    else {
        Write-Host "WARN: No birth.engine.version=BRO-v2 in $LogPath yet (starts on next birth run)." -ForegroundColor Yellow
    }
}
else {
    Write-Host "WARN: Log file not found: $LogPath" -ForegroundColor Yellow
}

Write-Host "Deploy gate PASSED." -ForegroundColor Green
exit 0
