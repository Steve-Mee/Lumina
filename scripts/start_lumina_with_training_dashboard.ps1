# Start LUMINA OS launcher + lumina_os Streamlit dashboard (training / first-boot / monitoring)
# in two separate PowerShell windows. Run from repo root: .\scripts\start_lumina_with_training_dashboard.ps1
param(
    [int]$LauncherPort = 8501,
    [int]$DashboardPort = 8502
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

# Child shells: escape $ so PYTHONPATH is set inside the new process, not here.
$launcherCmd = "`$env:PYTHONPATH='$repoRoot'; " +
    "`$env:LUMINA_CONFIG='$configYaml'; " +
    "Set-Location -LiteralPath '$repoRoot'; " +
    "& '$py' run_launcher.py --server.port $LauncherPort"

$dashboardCmd = "`$env:PYTHONPATH='$repoRoot'; " +
    "`$env:LUMINA_CONFIG='$configYaml'; " +
    "Set-Location -LiteralPath '$luminaOs'; " +
    "& '$py' -m streamlit run frontend/dashboard.py --server.port $DashboardPort"

Start-Process powershell -ArgumentList "-NoExit", "-Command", $launcherCmd
Start-Sleep -Milliseconds 350
Start-Process powershell -ArgumentList "-NoExit", "-Command", $dashboardCmd

Write-Host ""
Write-Host "LUMINA gestart in twee terminals:" -ForegroundColor Green
Write-Host "  Launcher (hoofdscherm):     http://localhost:$LauncherPort"
Write-Host "  Training / monitoring UI:   http://localhost:$DashboardPort  (map lumina_os/frontend/dashboard.py)"
Write-Host ""
Write-Host "Poorten bezet? Herstart met: .\scripts\start_lumina_with_training_dashboard.ps1 -LauncherPort 8510 -DashboardPort 8511"
Write-Host ""
