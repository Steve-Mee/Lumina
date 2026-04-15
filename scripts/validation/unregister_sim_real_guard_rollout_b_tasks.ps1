param(
    [string]$TaskPrefix = "Lumina-SIM-REAL-GUARD-RolloutB"
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[rollout-b-scheduler] $Message"
}

$tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "$TaskPrefix*" }
if (-not $tasks) {
    Write-Info "No tasks found for prefix $TaskPrefix"
    exit 0
}

foreach ($task in $tasks) {
    Unregister-ScheduledTask -TaskName $task.TaskName -Confirm:$false
    Write-Info "Removed $($task.TaskName)"
}

Write-Info "Rollout-B scheduled tasks removed."
