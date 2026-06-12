# Reset LUMINA onboarding state for local dev (first-install wizard testing).
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/reset-onboarding-dev.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/reset-onboarding-dev.ps1 -PartialBirth
param(
    [switch]$PartialBirth
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$StateDir = Join-Path $RepoRoot "state"
$EnvPath = Join-Path $RepoRoot ".env"
$EnvBackup = Join-Path $RepoRoot ".env.onboarding_reset.bak"
$SetupCompletePath = Join-Path $StateDir "lumina_setup_complete.json"
$PpoPolicyPath = Join-Path $RepoRoot "lumina_agents\ppo\lumina_ppo_policy.zip"

function Write-PhaseHint {
    param([string]$Label, [string[]]$Lines)
    Write-Host ""
    Write-Host $Label -ForegroundColor Green
    foreach ($line in $Lines) {
        Write-Host "  $line"
    }
}

if ($PartialBirth) {
    Write-Host "Partial birth reset in $RepoRoot (setup complete, birth incomplete)" -ForegroundColor Cyan

    if (-not (Test-Path $StateDir)) {
        New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
    }

    @{
        completed_at = (Get-Date).ToUniversalTime().ToString("o")
        source       = "reset-onboarding-dev.ps1 -PartialBirth"
    } | ConvertTo-Json | Set-Content -Path $SetupCompletePath -Encoding UTF8
    Write-Host "Wrote $SetupCompletePath"

    $partialRemove = @(
        "lumina_birth_completed.flag",
        "lumina_birth_certificate.json",
        "first_boot_go_to_bot.flag",
        "first_boot_user_configured.flag"
    )
    foreach ($name in $partialRemove) {
        $path = Join-Path $StateDir $name
        if (Test-Path $path) {
            Remove-Item $path -Force
            Write-Host "Removed $path"
        }
    }

    if (-not (Test-Path (Join-Path $StateDir "lumina_birth_progress.json"))) {
        @{
            status  = "interrupted"
            message = "Dev partial birth — resume expected on BirthPhaseScreen"
            progress = @{
                progress_pct = 42
                trades_done  = 1200
                target_trades = 25000
                stage = "training"
            }
        } | ConvertTo-Json -Depth 6 | Set-Content -Path (Join-Path $StateDir "lumina_birth_progress.json") -Encoding UTF8
        Write-Host "Seeded state/lumina_birth_progress.json (interrupted)"
    }

    if (Test-Path $PpoPolicyPath) {
        Remove-Item $PpoPolicyPath -Force
        Write-Host "Removed $PpoPolicyPath"
    }

    Write-PhaseHint "Expected after -PartialBirth (target lifecycle):" @(
        "  app_surface=birth (once Phase 1 wired)"
        "  BirthPhaseScreen with recovery — NOT wizard BirthActivateStep"
        "  Command Deck blocked until artifacts_ok"
    )
} else {
    Write-Host "Resetting onboarding dev state in $RepoRoot" -ForegroundColor Cyan

    $removeFiles = @(
        "lumina_setup_complete.json",
        "lumina_birth_completed.flag",
        "lumina_birth_certificate.json",
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

    Write-PhaseHint "Expected wizard flow after full reset:" @(
        "1. Welcome"
        "2. Smart Setup (if Ollama/model missing)"
        "3. Credentials"
        "4. Quick Configuration"
        "5. Birth Activate"
    )
}

Write-Host ""
Write-Host "Start backend:" -ForegroundColor Yellow
Write-Host "  cd lumina_os; `$env:PYTHONPATH='$RepoRoot'; python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000"
Write-Host "Start Tauri:" -ForegroundColor Yellow
Write-Host "  cd tauri-app; npm run tauri dev"
