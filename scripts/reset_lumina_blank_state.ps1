param(
    [switch]$SkipProcessStop
)

# Post-setup reset: behoudt setup-state bestanden (lumina_setup_complete/status, hardware snapshot, admin/model state).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $repoRoot "backups\reset_$timestamp"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

function Backup-Path {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )
    $source = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source)) {
        return
    }
    $target = Join-Path $backupRoot $RelativePath
    $targetParent = Split-Path -Parent $target
    if ($targetParent -and -not (Test-Path -LiteralPath $targetParent)) {
        New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
}

if (-not $SkipProcessStop) {
    $ports = @(8000, 8501, 8502)
    foreach ($port in $ports) {
        $lines = netstat -ano | Select-String ":$port" | Select-String "LISTENING"
        foreach ($line in $lines) {
            $procId = ($line.ToString().Trim() -split '\s+')[-1]
            if ($procId -and $procId -match '^[0-9]+$') {
                try {
                    Stop-Process -Id ([int]$procId) -Force -ErrorAction Stop
                } catch {
                }
            }
        }
    }
    Start-Sleep -Milliseconds 800
}

$backupTargets = @(
    "state",
    "logs",
    "journal\simulator",
    "lumina_os\logs",
    "lumina_os\state\metrics.db",
    "lumina_agents\ppo\lumina_ppo_policy.zip",
    "lumina_agents\ppo\lumina_ppo_policy_practice.zip",
    "state\lumina_birth_completed.flag",
    "state\lumina_birth_practice_completed.flag",
    "state\first_boot_completed.flag",
    "state\ppo_policy_metadata.json",
    "state\lumina_birth_progress.json",
    "state\lumina_birth_checkpoint.json",
    "state\first_boot_progress.json"
)

foreach ($item in $backupTargets) {
    Backup-Path -RelativePath $item
}

$wipeDirectories = @(
    "logs",
    "journal\simulator",
    "lumina_os\logs"
)

foreach ($relativeDir in $wipeDirectories) {
    $fullDir = Join-Path $repoRoot $relativeDir
    if (-not (Test-Path -LiteralPath $fullDir)) {
        New-Item -ItemType Directory -Path $fullDir -Force | Out-Null
        continue
    }
    Get-ChildItem -LiteralPath $fullDir -Force -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$stateDir = Join-Path $repoRoot "state"
$preserveStateFiles = @(
    "lumina_setup_complete.json",
    "lumina_setup_status.json",
    "hardware_snapshot.json",
    "launcher_admin_password.json",
    "model_catalog_state.json"
)
if (-not (Test-Path -LiteralPath $stateDir)) {
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
}
Get-ChildItem -LiteralPath $stateDir -Force -ErrorAction SilentlyContinue | ForEach-Object {
    if ($preserveStateFiles -contains $_.Name) {
        return
    }
    Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
}

$deleteTargets = @(
    "lumina_os\state\metrics.db",
    "lumina_agents\ppo\lumina_ppo_policy.zip",
    "lumina_agents\ppo\lumina_ppo_policy_practice.zip",
    "state\lumina_birth_completed.flag",
    "state\lumina_birth_practice_completed.flag",
    "state\first_boot_completed.flag",
    "state\ppo_policy_metadata.json",
    "state\lumina_birth_progress.json",
    "state\lumina_birth_checkpoint.json",
    "state\first_boot_progress.json",
    "state\monitoring_debug_training_process.json",
    "state\trade_reconciler_status.json"
)

foreach ($relativePath in $deleteTargets) {
    $fullPath = Join-Path $repoRoot $relativePath
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "LUMINA full reset completed." -ForegroundColor Green
Write-Host "Backup saved to: $backupRoot"
Write-Host "State/log/history cleared and first-boot policy artifacts removed (setup-state preserved)."
Write-Host ""
