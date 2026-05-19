# Build LUMINA Core Tauri desktop app with signing env loaded from repo .env
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

function Import-DotEnv {
    param([string]$Path)
    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ($key) {
            $values[$key] = $value
        }
    }
    return $values
}

$envFile = Join-Path $RepoRoot ".env"
$envValues = Import-DotEnv -Path $envFile

$keyPathSetting = $envValues["TAURI_SIGNING_PRIVATE_KEY_PATH"]
if ($keyPathSetting) {
    $resolvedKeyPath = if ([System.IO.Path]::IsPathRooted($keyPathSetting)) {
        $keyPathSetting
    } else {
        Join-Path $RepoRoot $keyPathSetting
    }
    if (-not (Test-Path $resolvedKeyPath)) {
        Write-Error "TAURI_SIGNING_PRIVATE_KEY_PATH points to missing file: $resolvedKeyPath"
    }
    $env:TAURI_SIGNING_PRIVATE_KEY_PATH = $resolvedKeyPath
    Write-Host "Using Tauri signing key: $resolvedKeyPath"
} else {
    Write-Warning "TAURI_SIGNING_PRIVATE_KEY_PATH not set in .env — build may fail at updater signing step."
}

$tauriDir = Join-Path $RepoRoot "tauri-app"
Push-Location $tauriDir
try {
    npm run tauri build
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
