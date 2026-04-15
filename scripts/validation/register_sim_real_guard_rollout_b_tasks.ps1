param(
    [Parameter(Mandatory = $true)]
    [string]$ControlRoot,
    [Parameter(Mandatory = $true)]
    [string]$CandidateRoot,
    [Parameter(Mandatory = $true)]
    [string]$CrossTradeToken,
    [Parameter(Mandatory = $true)]
    [string]$CrossTradeAccount,
    [string]$StartDate,
    [int]$TradingDays = 5,
    [string]$Broker = "live",
    [string]$TaskPrefix = "Lumina-SIM-REAL-GUARD-RolloutB",
    [string]$PythonExe = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[rollout-b-scheduler] $Message"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found: $pythonExe"
}

$scheduleOut = Join-Path $repoRoot "state\validation\sim_real_guard_rollout_b\schedule_plan.json"
$buildArgs = @(
    "scripts/validation/build_sim_real_guard_rollout_b_schedule.py",
    "--trading-days", "$TradingDays",
    "--output", $scheduleOut
)
if ($StartDate) {
    $buildArgs += @("--start-date", $StartDate)
}

Write-Info "Building rollout-B schedule plan..."
& $pythonExe @buildArgs
if ($LASTEXITCODE -ne 0) {
    throw "Failed to build schedule plan"
}

$plan = Get-Content $scheduleOut -Raw | ConvertFrom-Json
foreach ($window in $plan.windows) {
    $taskName = "$TaskPrefix-$($window.task_name_suffix)"
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        if (-not $Force) {
            throw "Task already exists: $taskName (use -Force to replace)"
        }
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    $script = Join-Path $repoRoot "scripts\validation\run_rollout_b_window.ps1"
    $argString = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", ('"{0}"' -f $script),
        "-ControlRoot", ('"{0}"' -f $ControlRoot),
        "-CandidateRoot", ('"{0}"' -f $CandidateRoot),
        "-WindowLabel", $window.window_label,
        "-Duration", $window.duration,
        "-Broker", $Broker,
        "-PythonExe", ('"{0}"' -f $(if ($PythonExe) { $PythonExe } else { $pythonExe })),
        "-CrossTradeToken", ('"{0}"' -f $CrossTradeToken),
        "-CrossTradeAccount", ('"{0}"' -f $CrossTradeAccount)
    ) -join " "

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argString -WorkingDirectory $repoRoot
    $triggerTime = [datetime]::Parse($window.start_local)
    $trigger = New-ScheduledTaskTrigger -Once -At $triggerTime
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
    Write-Info "Registered $taskName at $($window.start_local)"
}

Write-Info "All rollout-B tasks registered successfully."
