param(
    [Parameter(Mandatory = $true)]
    [string]$ControlRoot,
    [Parameter(Mandatory = $true)]
    [string]$CandidateRoot,
    [Parameter(Mandatory = $true)]
    [string]$WindowLabel,
    [Parameter(Mandatory = $true)]
    [string]$CrossTradeToken,
    [Parameter(Mandatory = $true)]
    [string]$CrossTradeAccount,
    [string]$Duration = "30m",
    [string]$Broker = "live",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[rollout-b-window] $Message"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found: $pythonExe"
}

Write-Info "Running automated rollout window $WindowLabel"
& $pythonExe "scripts/validation/run_sim_real_guard_rollout_b.py" `
    --control-root $ControlRoot `
    --candidate-root $CandidateRoot `
    --window-label $WindowLabel `
    --duration $Duration `
    --broker $Broker `
    --crosstrade-token $CrossTradeToken `
    --crosstrade-account $CrossTradeAccount `
    --python-exe $(if ($PythonExe) { $PythonExe } else { $pythonExe })

exit $LASTEXITCODE
