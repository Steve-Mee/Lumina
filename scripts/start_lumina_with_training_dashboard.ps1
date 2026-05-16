# Start LUMINA OS in single-screen mode (launcher on 8501) and backend on 8000.
# Optional: start legacy standalone dashboard (8502) via -StartLegacyDashboard.
# Run from repo root: .\scripts\start_lumina_with_training_dashboard.ps1
param(
    [int]$LauncherPort = 8501,
    [int]$DashboardPort = 8502,
    [switch]$StartLegacyDashboard
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    $py = "python"
}

$luminaOs = Join-Path $repoRoot "lumina_os"
$configYaml = Join-Path $repoRoot "config.yaml"
if (-not (Test-Path -LiteralPath $luminaOs)) {
    throw "Expected folder not found: $luminaOs"
}

# Child shells: escape $ so PYTHONPATH is set inside the new process, not here.
$backendCmd = "`$env:PYTHONPATH='$repoRoot'; " +
    "`$env:LUMINA_CONFIG='$configYaml'; " +
    "`$env:LUMINA_PYTHON='$py'; " +
    "Set-Location -LiteralPath '$luminaOs'; " +
    "& '$py' -m uvicorn backend.app:app --host 127.0.0.1 --port 8000"

$launcherCmd = "`$env:PYTHONPATH='$repoRoot'; " +
    "`$env:LUMINA_CONFIG='$configYaml'; " +
    "`$env:LUMINA_PYTHON='$py'; " +
    "Set-Location -LiteralPath '$repoRoot'; " +
    "& '$py' run_launcher.py --server.port $LauncherPort --server.fileWatcherType none"

$dashboardCmd = "`$env:PYTHONPATH='$repoRoot'; " +
    "`$env:LUMINA_CONFIG='$configYaml'; " +
    "`$env:LUMINA_PYTHON='$py'; " +
    "Set-Location -LiteralPath '$luminaOs'; " +
    "& '$py' -m streamlit run frontend/dashboard.py --server.port $DashboardPort --server.fileWatcherType none"

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Start-Sleep -Milliseconds 350
Start-Process powershell -ArgumentList "-NoExit", "-Command", $launcherCmd

if ($StartLegacyDashboard.IsPresent) {
    Start-Sleep -Milliseconds 350
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $dashboardCmd
}

Write-Host ""
Write-Host "LUMINA gestart in single-screen modus:" -ForegroundColor Green
Write-Host "  Backend API:                http://localhost:8000"
Write-Host "  Launcher (hoofdscherm):     http://localhost:$LauncherPort"
if ($StartLegacyDashboard.IsPresent) {
    Write-Host "  Legacy dashboard (optioneel): http://localhost:$DashboardPort"
}
Write-Host ""
Write-Host "Legacy dashboard nodig? Gebruik: .\scripts\start_lumina_with_training_dashboard.ps1 -StartLegacyDashboard"
Write-Host ""
