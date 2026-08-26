#Requires -Version 5.1
<#
.SYNOPSIS
  Generate and install LUMINA_FABRIC_TOKEN for Brain + NT8 Execution Fabric.

.DESCRIPTION
  - Generates a cryptographically strong url-safe secret (or uses -Token)
  - Writes User-level environment variable LUMINA_FABRIC_TOKEN (NT8 sees it after restart)
  - Upserts workspace .env
  - Writes %APPDATA%\LUMINA\fabric.json (defaults, no secret value)
  - Sets process-level env for the current shell

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install_fabric_token.ps1
  powershell -ExecutionPolicy Bypass -File scripts\install_fabric_token.ps1 -Token "already-generated"
#>
[CmdletBinding()]
param(
    [string]$Token = "",
    [string]$WorkspaceRoot = "",
    [switch]$SkipUserEnv,
    [switch]$SkipEnvFile,
    [switch]$SkipFabricJson
)

$ErrorActionPreference = "Stop"

function New-FabricToken {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    $b64 = [Convert]::ToBase64String($bytes)
    return ($b64 -replace '\+', '-' -replace '/', '_' -replace '=+$', '')
}

function Upsert-DotEnvLine {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value
    )
    $line = "$Key=$Value"
    if (-not (Test-Path -LiteralPath $Path)) {
        Set-Content -LiteralPath $Path -Value $line -Encoding UTF8
        return
    }
    $content = Get-Content -LiteralPath $Path -ErrorAction Stop
    $found = $false
    $out = foreach ($row in $content) {
        if ($row -match "^\s*$([regex]::Escape($Key))\s*=") {
            $found = $true
            $line
        }
        else {
            $row
        }
    }
    if (-not $found) {
        $out = @($out) + $line
    }
    Set-Content -LiteralPath $Path -Value $out -Encoding UTF8
}

if (-not $WorkspaceRoot) {
    $WorkspaceRoot = Split-Path -Parent $PSScriptRoot
}
$WorkspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).Path

if (-not $Token) {
    $Token = New-FabricToken
    Write-Host "[fabric-token] Generated new LUMINA_FABRIC_TOKEN"
}
else {
    Write-Host "[fabric-token] Using provided token"
}

# Process scope (current shell / child processes)
$env:LUMINA_FABRIC_TOKEN = $Token

if (-not $SkipUserEnv) {
    [Environment]::SetEnvironmentVariable("LUMINA_FABRIC_TOKEN", $Token, "User")
    Write-Host "[fabric-token] User environment LUMINA_FABRIC_TOKEN set (restart NinjaTrader to pick up)"
}

if (-not $SkipEnvFile) {
    $envPath = Join-Path $WorkspaceRoot ".env"
    Upsert-DotEnvLine -Path $envPath -Key "LUMINA_FABRIC_TOKEN" -Value $Token
    Write-Host "[fabric-token] Upserted $envPath"
}

if (-not $SkipFabricJson) {
    $luminaDir = Join-Path $env:APPDATA "LUMINA"
    if (-not (Test-Path -LiteralPath $luminaDir)) {
        New-Item -ItemType Directory -Path $luminaDir -Force | Out-Null
    }
    $fabricPath = Join-Path $luminaDir "fabric.json"
    $payload = [ordered]@{
        BindHost             = "127.0.0.1"
        BindPort             = 50051
        AuthTokenEnv         = "LUMINA_FABRIC_TOKEN"
        AccountName          = "Sim101"
        GatewayMode          = "nt"
        HeartbeatTimeoutMs   = 5000
        FlattenGraceMs       = 15000
        FlattenOnTimeout     = $true
        BindLocalhostOnly    = $true
        MaxPositionSize      = 2
        MaxOrdersPerMinute   = 30
        DailyLossLimit       = 0
    }
    if (Test-Path -LiteralPath $fabricPath) {
        try {
            $existing = Get-Content -LiteralPath $fabricPath -Raw | ConvertFrom-Json
            foreach ($prop in @("GatewayMode", "BindHost", "BindPort", "AccountName", "AuthTokenEnv")) {
                if ($null -ne $existing.$prop -and "$($existing.$prop)" -ne "") {
                    $payload[$prop] = $existing.$prop
                }
            }
            # Legacy "sim" meant Sim101 account path — promote to explicit nt.
            $gw = ("$($payload.GatewayMode)").ToLowerInvariant()
            if ($gw -eq "sim" -or $gw -eq "sim101" -or $gw -eq "") {
                $payload.GatewayMode = "nt"
            }
        }
        catch {
            Write-Warning "[fabric-token] Could not merge existing fabric.json; rewriting defaults"
        }
    }
    # UTF-8 without BOM (C# / Python json.loads both happy)
    $json = ($payload | ConvertTo-Json -Depth 4) + "`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($fabricPath, $json, $utf8NoBom)
    Write-Host "[fabric-token] Wrote $fabricPath (no secret value stored in file)"
}

Write-Host ""
Write-Host "[fabric-token] Done. Next steps:"
Write-Host "  1. Restart NinjaTrader 8 if it is running (User env)."
Write-Host "  2. Start ONE fabric host (SimHost OR NT8 AddOn) on 127.0.0.1:50051."
Write-Host "  3. Start Lumina backend / Brain with the same token from .env."
Write-Host "  4. Do not commit .env or fabric.json secrets."
Write-Host ""
Write-Host "[fabric-token] Token length: $($Token.Length) (value not printed)"
