# Start LUMINA backend + Neural Command Deck instructions (Streamlit removed).
# Run from repo root: .\scripts\start_lumina_with_training_dashboard.ps1
param(
    [switch]$StartTauriDev
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

$backendCmd = "`$env:PYTHONPATH='$repoRoot'; " +
    "`$env:LUMINA_CONFIG='$configYaml'; " +
    "`$env:LUMINA_PYTHON='$py'; " +
    "Set-Location -LiteralPath '$luminaOs'; " +
    "& '$py' -m uvicorn backend.app:app --host 127.0.0.1 --port 8000"

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

if ($StartTauriDev.IsPresent) {
    $tauriDir = Join-Path $repoRoot "tauri-app"
    $tauriCmd = "Set-Location -LiteralPath '$tauriDir'; npm run tauri dev"
    Start-Sleep -Milliseconds 350
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $tauriCmd
}

Write-Host ""
Write-Host "LUMINA backend gestart:" -ForegroundColor Green
Write-Host "  Backend API: http://localhost:8000"
Write-Host ""
Write-Host "Start Neural Command Deck (Tauri) in een nieuwe terminal:"
Write-Host "  cd tauri-app"
Write-Host "  npm run tauri dev"
Write-Host ""
Write-Host "Optioneel met deze script: .\scripts\start_lumina_with_training_dashboard.ps1 -StartTauriDev"
Write-Host ""
