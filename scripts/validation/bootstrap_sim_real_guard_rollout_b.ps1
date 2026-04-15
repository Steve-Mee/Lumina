param(
    [Parameter(Mandatory = $true)]
    [string]$ControlRoot,
    [Parameter(Mandatory = $true)]
    [string]$CandidateRoot,
    [string]$SourceRoot = "",
    [string]$CrossTradeToken = "",
    [string]$CrossTradeAccount = "",
    [string]$Broker = "live",
    [string]$StartDate,
    [int]$TradingDays = 5,
    [string]$TaskPrefix = "Lumina-SIM-REAL-GUARD-RolloutB",
    [switch]$RegisterTasks,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[rollout-b-bootstrap] $Message"
}

$repoRoot = if ($SourceRoot) { (Resolve-Path $SourceRoot).Path } else { (Resolve-Path (Join-Path $PSScriptRoot "..\.." )).Path }
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found: $pythonExe"
}

Write-Info "Bootstrapping isolated rollout-B workspaces..."
& $pythonExe "scripts/validation/bootstrap_sim_real_guard_rollout_b_workspaces.py" `
    --source-root $repoRoot `
    --control-root $ControlRoot `
    --candidate-root $CandidateRoot `
    --broker $Broker `
    --crosstrade-token $CrossTradeToken `
    --crosstrade-account $CrossTradeAccount `
    --shared-python-exe $pythonExe

if ($LASTEXITCODE -ne 0) {
    throw "Workspace bootstrap failed"
}

if ($RegisterTasks) {
    if (-not $CrossTradeToken -or -not $CrossTradeAccount) {
        throw "-RegisterTasks requires -CrossTradeToken and -CrossTradeAccount"
    }
    Write-Info "Registering rollout-B tasks..."
    $registerScript = Join-Path $repoRoot "scripts\validation\register_sim_real_guard_rollout_b_tasks.ps1"
    & $registerScript `
        -ControlRoot $ControlRoot `
        -CandidateRoot $CandidateRoot `
        -CrossTradeToken $CrossTradeToken `
        -CrossTradeAccount $CrossTradeAccount `
        -StartDate $StartDate `
        -TradingDays $TradingDays `
        -Broker $Broker `
        -TaskPrefix $TaskPrefix `
        -PythonExe $pythonExe `
        -Force:$Force

    if ($LASTEXITCODE -ne 0) {
        throw "Task registration failed"
    }
}

Write-Info "Bootstrap completed successfully."