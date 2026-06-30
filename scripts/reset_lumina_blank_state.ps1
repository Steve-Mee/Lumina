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
    $ports = @(8000, 1420)
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
    "lumina_agents\ppo"
)

foreach ($item in $backupTargets) {
    Backup-Path -RelativePath $item
}

$pythonCmd = $null
foreach ($candidate in @("py", "python")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $pythonCmd = $candidate
        break
    }
}
if (-not $pythonCmd) {
    throw "Python not found on PATH (tried py, python)."
}

$env:PYTHONPATH = $repoRoot
& $pythonCmd -m lumina_launcher.core.birth_reset --workspace $repoRoot
if ($LASTEXITCODE -ne 0) {
    throw "Birth training reset failed (exit $LASTEXITCODE)."
}

$stateDir = Join-Path $repoRoot "state"
$preserveStateFiles = @(
    "lumina_setup_complete.json",
    "lumina_setup_status.json",
    "hardware_snapshot.json",
    "launcher_admin_password.json",
    "model_catalog_state.json",
    "first_boot_user_configured.flag"
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

Write-Host ""
Write-Host "LUMINA full reset completed." -ForegroundColor Green
Write-Host "Backup saved to: $backupRoot"
Write-Host "Birth training state cleared via Python SSOT (setup-state preserved)."
Write-Host ""
