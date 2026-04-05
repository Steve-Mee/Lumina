param(
    [switch]$RunInWsl,
    [string]$WslDistro
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[lumina-smoke-helper] $Message"
}

function Convert-ToWslPath([string]$WindowsPath) {
    $normalized = $WindowsPath -replace "\\", "/"
    if ($normalized -match "^([A-Za-z]):/(.*)$") {
        $drive = $matches[1].ToLower()
        $rest = $matches[2]
        return "/mnt/$drive/$rest"
    }
    return $normalized
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$wslRepoRoot = Convert-ToWslPath $repoRoot
$smokeScript = "deploy/smoke_preprod.sh"
$wslCommand = "cd '$wslRepoRoot' && bash $smokeScript"

Write-Info "Windows detected. Pre-prod smoke script should run on Linux target or WSL with Docker Linux engine."
Write-Info "Recommended command on Linux host: bash deploy/smoke_preprod.sh"

$wsl = Get-Command wsl -ErrorAction SilentlyContinue
if (-not $wsl) {
    Write-Info "WSL not found. Run this command on the Linux pre-prod machine: bash deploy/smoke_preprod.sh"
    exit 0
}

if ($RunInWsl) {
    Write-Info "Attempting to run smoke script inside WSL..."

    if ($WslDistro) {
        & wsl -d $WslDistro -- bash -lc $wslCommand
    }
    else {
        & wsl -- bash -lc $wslCommand
    }

    if ($LASTEXITCODE -ne 0) {
        throw "WSL smoke execution failed with exit code $LASTEXITCODE"
    }

    Write-Info "WSL smoke execution completed successfully."
    exit 0
}

Write-Info "To run directly from this Windows shell via WSL:"
if ($WslDistro) {
    Write-Info "  .\\deploy\\run_preprod_smoke.ps1 -RunInWsl -WslDistro '$WslDistro'"
}
else {
    Write-Info "  .\\deploy\\run_preprod_smoke.ps1 -RunInWsl"
}
