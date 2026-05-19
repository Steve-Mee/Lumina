# Reset LUMINA onboarding state for local dev (first-install wizard testing).
# Usage: powershell -ExecutionPolicy Bypass -File scripts/reset-onboarding-dev.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$StateDir = Join-Path $RepoRoot "state"
$EnvPath = Join-Path $RepoRoot ".env"
$EnvBackup = Join-Path $RepoRoot ".env.onboarding_reset.bak"

Write-Host "Resetting onboarding dev state in $RepoRoot" -ForegroundColor Cyan

$removeFiles = @(
    "lumina_setup_complete.json",
    "lumina_birth_completed.flag",
    "first_boot_go_to_bot.flag",
    "first_boot_user_configured.flag",
    "lumina_birth_progress.json",
    "lumina_birth_checkpoint.json"
)

foreach ($name in $removeFiles) {
    $path = Join-Path $StateDir $name
    if (Test-Path $path) {
        Remove-Item $path -Force
        Write-Host "Removed $path"
    }
}

if (Test-Path $EnvPath) {
    Copy-Item $EnvPath $EnvBackup -Force
    $lines = Get-Content $EnvPath
    $stripKeys = @(
        "LUMINA_JWT_SECRET_KEY",
        "CROSSTRADE_TOKEN",
        "CROSSTRADE_ACCOUNT",
        "LUMINA_ADMIN_API_KEY"
    )
    $filtered = $lines | Where-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return $true }
        $keep = $true
        foreach ($key in $stripKeys) {
            if ($line -match "^\Q$key\E=") { $keep = $false; break }
        }
        $keep
    }
    Set-Content -Path $EnvPath -Value $filtered -Encoding UTF8
    Write-Host "Stripped credential keys from .env (backup: $EnvBackup)"
}

Write-Host ""
Write-Host "Expected wizard flow after reset:" -ForegroundColor Green
Write-Host "  1. Welcome"
Write-Host "  2. Smart Setup (if Ollama/model missing)"
Write-Host "  3. Credentials"
Write-Host "  4. Quick Configuration"
Write-Host "  5. Birth Activate"
Write-Host ""
Write-Host "Start backend:" -ForegroundColor Yellow
Write-Host "  cd lumina_os; `$env:PYTHONPATH='$RepoRoot'; python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000"
Write-Host "Start Tauri:" -ForegroundColor Yellow
Write-Host "  cd tauri-app; npm run tauri dev"
