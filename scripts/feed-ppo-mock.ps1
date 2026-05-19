# Appends mock PPO evolution JSONL lines for frontend/deck testing.
# Requires backend tailer watching state/ppo_training_log.jsonl.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $repoRoot "state\ppo_training_log.jsonl"
$stateDir = Split-Path -Parent $logPath

if (-not (Test-Path $stateDir)) {
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
}

$startStep = 5000
if (Test-Path $logPath) {
    $lastLine = Get-Content $logPath -Tail 1 -ErrorAction SilentlyContinue
    if ($lastLine) {
        try {
            $parsed = $lastLine | ConvertFrom-Json
            if ($parsed.step) {
                $startStep = [int]$parsed.step + 5000
            }
        } catch {
            Write-Warning "Could not parse last JSONL line; starting at step 5000."
        }
    }
}

$lines = @()
for ($i = 0; $i -lt 15; $i++) {
    $step = $startStep + ($i * 5000)
    $reward = [math]::Round(0.35 + ($i * 0.04), 3)
    $entropy = [math]::Round(0.85 - ($i * 0.03), 3)
    $winrate = [math]::Round(0.48 + ($i * 0.02), 3)
    $sharpe = [math]::Round(0.9 + ($i * 0.08), 2)
    $long = [math]::Round(0.35 + ($i * 0.02), 2)
    $short = [math]::Round(0.30 - ($i * 0.01), 2)
    $hold = [math]::Round(1.0 - $long - $short, 2)
    if ($hold -lt 0) { $hold = 0.1; $long = 0.45; $short = 0.45 }

    $entry = [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssK")
        step = $step
        mean_reward = $reward
        policy_loss = [math]::Round(0.05 + ($i * 0.008), 4)
        value_loss = [math]::Round(0.09 + ($i * 0.01), 4)
        entropy = $entropy
        explained_variance = [math]::Round(0.55 + ($i * 0.02), 3)
        winrate_rolling_5k = $winrate
        sharpe_rolling_5k = $sharpe
        action_distribution = [ordered]@{
            long = $long
            short = $short
            hold = $hold
        }
        avg_stop_pct = 0.009
        avg_target_pct = 0.018
    }

    $lines += ($entry | ConvertTo-Json -Compress)
}

Add-Content -Path $logPath -Value $lines -Encoding utf8
Write-Host "Appended $($lines.Count) mock PPO lines to $logPath (from step $startStep)."
