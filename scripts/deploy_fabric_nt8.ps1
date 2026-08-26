# Deploy LUMINA Execution Fabric to live NinjaTrader 8 Custom folder.
# Code Red: never dual-load bridge (NtBridge only). Never force-overwrite while NT runs.
# Capital preservation: Sim only.

$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $repo "integrations\ninjatrader8"))) {
    $repo = "C:\ninjatraderai_bot"
}

$myDocs = [Environment]::GetFolderPath("MyDocuments")
$custom = Join-Path $myDocs "NinjaTrader 8\bin\Custom"
$addons = Join-Path $custom "AddOns"
Write-Host "My Documents : $myDocs"
Write-Host "NT Custom    : $custom"

if (-not (Test-Path $custom)) {
    throw "NinjaTrader Custom folder not found: $custom - is NT8 installed/run once?"
}

$ntRunning = $null -ne (Get-Process -Name "NinjaTrader*" -ErrorAction SilentlyContinue)
if ($ntRunning) {
    Write-Host "NinjaTrader is RUNNING - will STAGE *.dll.new only (no in-place overwrite)."
}

$srcCandidates = @(
    (Join-Path $repo "integrations\ninjatrader8\LuminaNt8AddOn\bin\Release\net48"),
    (Join-Path $repo "integrations\ninjatrader8\deploy\AddOns"),
    (Join-Path $repo "integrations\ninjatrader8\Lumina.Execution.Fabric\bin\Release\net48")
)

# Single bridge name only — dual LuminaNt8AddOn.dll + NtBridge loads both vendor assemblies.
$files = @(
    "Lumina.Fabric.NtBridge.dll",
    "Lumina.Execution.Fabric.dll",
    "Google.Protobuf.dll", "Grpc.Core.dll", "Grpc.Core.Api.dll",
    "grpc_csharp_ext.x64.dll", "grpc_csharp_ext.x86.dll",
    "System.Memory.dll", "System.Buffers.dll", "System.Runtime.CompilerServices.Unsafe.dll",
    "System.Threading.Tasks.Extensions.dll", "System.Numerics.Vectors.dll", "System.ValueTuple.dll",
    "Microsoft.Bcl.AsyncInterfaces.dll", "System.Text.Json.dll", "System.Text.Encodings.Web.dll"
)

# Product NtBridge must include NT Account + historical + live types (~50KB+).
$BridgeMinBytes = 40000
$RequiredMarkers = @("FabricNtHost", "NtAccountOrderGateway", "NtHistoricalDataProvider", "NtLiveMarketDataProvider")

function Test-NtBridgeProduct {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -lt $BridgeMinBytes) {
        Write-Warning "Reject bridge (too small $($item.Length) < $BridgeMinBytes): $Path"
        return $false
    }
    $bytes = [IO.File]::ReadAllBytes($item.FullName)
    $text = [Text.Encoding]::ASCII.GetString($bytes)
    foreach ($m in $RequiredMarkers) {
        if ($text.IndexOf($m) -lt 0) {
            Write-Warning "Reject bridge (missing $m): $Path"
            return $false
        }
    }
    return $true
}

New-Item -ItemType Directory -Path $addons -Force | Out-Null
$copied = 0
$bridgeSrc = $null
$bridgeBestSize = -1
foreach ($dir in $srcCandidates) {
    foreach ($n in @("Lumina.Fabric.NtBridge.dll", "LuminaNt8AddOn.dll")) {
        $p = Join-Path $dir $n
        if ((Test-Path $p) -and (Test-NtBridgeProduct $p)) {
            $sz = (Get-Item $p).Length
            if ($sz -gt $bridgeBestSize) {
                $bridgeSrc = $p
                $bridgeBestSize = $sz
            }
        }
    }
}
if (-not $bridgeSrc) {
    throw "No product-complete Lumina.Fabric.NtBridge.dll found (build with NINJATRADER8_BIN). Need >= $BridgeMinBytes bytes + type markers."
}
Write-Host "Bridge source : $bridgeSrc ($bridgeBestSize bytes)"

function Copy-OrStage {
    param([string]$Src, [string]$DestDir, [string]$Name)
    $dest = Join-Path $DestDir $Name
    $stage = Join-Path $DestDir ($Name + ".new")
    if ($script:ntRunning) {
        Copy-Item $Src $stage -Force
        Write-Host "  STAGED $Name.new (NT running)"
        return
    }
    try {
        Copy-Item $Src $dest -Force
        Write-Host "  OK $Name"
    } catch {
        Copy-Item $Src $stage -Force
        Write-Warning "Locked $Name - staged as $Name.new (close NT and re-run)"
    }
}

foreach ($name in $files) {
    $src = $null
    foreach ($dir in $srcCandidates) {
        $p = Join-Path $dir $name
        if (Test-Path $p) { $src = $p; break }
    }
    if (-not $src -and $bridgeSrc -and $name -eq "Lumina.Fabric.NtBridge.dll") {
        $src = $bridgeSrc
    }
    if (-not $src) {
        Write-Warning "Missing $name"
        continue
    }
    Copy-OrStage -Src $src -DestDir $custom -Name $name
    Copy-OrStage -Src $src -DestDir $addons -Name $name
    $copied++
}

# Quarantine ANY active LuminaNt8AddOn.dll alias (dual load risk)
foreach ($dir in @($custom, $addons)) {
    $alias = Join-Path $dir "LuminaNt8AddOn.dll"
    if (Test-Path $alias) {
        try {
            Move-Item $alias (Join-Path $dir "LuminaNt8AddOn.dll.DUAL_DISABLE") -Force
            Write-Host "  QUARANTINED dual alias $alias"
        } catch {
            Write-Warning "Could not quarantine LuminaNt8AddOn.dll (close NT): $_"
        }
    }
}

$stub = Join-Path $repo "integrations\ninjatrader8\deploy\LuminaNt8AddOn.stub.cs"
if (Test-Path $stub) {
    Copy-Item $stub (Join-Path $custom "LuminaNt8AddOn.cs") -Force
    Write-Host "  OK LuminaNt8AddOn.cs (stub)"
}

$stubSrc = Join-Path $repo "integrations\ninjatrader8\deploy\AddOns\@LuminaFabricHost.cs"
if (Test-Path $stubSrc) {
    Copy-Item $stubSrc (Join-Path $addons "@LuminaFabricHost.cs") -Force
    Write-Host "  OK @LuminaFabricHost.cs (source AddOn)"
}

# Promote staged *.dll.new ONLY when NT is not running.
# CRITICAL: never promote a stub NtBridge over a good product DLL.
function Promote-StagedDlls {
    param([string]$Dir)
    Get-ChildItem $Dir -Filter "*.dll.new" -ErrorAction SilentlyContinue | ForEach-Object {
        $finalName = $_.BaseName  # e.g. Lumina.Fabric.NtBridge.dll
        $final = Join-Path $Dir $finalName
        if ($finalName -eq "Lumina.Fabric.NtBridge.dll") {
            if (-not (Test-NtBridgeProduct $_.FullName)) {
                $q = Join-Path $Dir "Lumina.Fabric.NtBridge.dll.new.STUB_DISABLE"
                try {
                    Move-Item $_.FullName $q -Force
                    Write-Warning "Quarantined stub staged bridge: $q"
                } catch {
                    Write-Warning "Could not quarantine stub staged bridge: $_"
                }
                return
            }
            # If active already product-complete and staged is not larger, drop staged.
            if ((Test-Path $final) -and (Test-NtBridgeProduct $final)) {
                $act = (Get-Item $final).Length
                $stg = (Get-Item $_.FullName).Length
                if ($stg -le $act) {
                    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
                    Write-Host "  SKIP promote NtBridge.new (active already product $act bytes)"
                    return
                }
            }
        }
        try {
            Move-Item $_.FullName $final -Force
            Write-Host "  PROMOTED $($_.Name) -> $finalName"
        } catch {
            Write-Warning "Could not promote $($_.Name): $_"
        }
    }
}

if (-not $ntRunning) {
    Promote-StagedDlls -Dir $custom
    Promote-StagedDlls -Dir $addons
} else {
    Write-Host "  SKIP promote *.dll.new (NT still running)"
}

# Post-deploy integrity (active or staged)
$bridgeDest = Join-Path $custom "Lumina.Fabric.NtBridge.dll"
$bridgeStage = Join-Path $custom "Lumina.Fabric.NtBridge.dll.new"
$checkBridge = if (Test-Path $bridgeDest) { $bridgeDest } elseif (Test-Path $bridgeStage) { $bridgeStage } else { $null }
if ($null -eq $checkBridge -or -not (Test-NtBridgeProduct $checkBridge)) {
    # Last-chance: force-copy product bridge now that stub .new is gone.
    if (-not $ntRunning -and $bridgeSrc) {
        Copy-Item $bridgeSrc $bridgeDest -Force
        Copy-Item $bridgeSrc (Join-Path $addons "Lumina.Fabric.NtBridge.dll") -Force
        $checkBridge = $bridgeDest
    }
}
if ($null -eq $checkBridge -or -not (Test-NtBridgeProduct $checkBridge)) {
    throw "Post-deploy integrity FAILED for NtBridge at $custom - refuse incomplete product deploy."
}
$checkLen = (Get-Item -LiteralPath $checkBridge).Length
Write-Host "Integrity OK  : $checkBridge ($checkLen bytes)"

# Also sync secondary trees (Documents vs OneDrive Documenten) when present
$secondary = @(
    (Join-Path $env:USERPROFILE "OneDrive\Documenten\NinjaTrader 8\bin\Custom"),
    (Join-Path $env:USERPROFILE "OneDrive\Documents\NinjaTrader 8\bin\Custom"),
    (Join-Path $env:USERPROFILE "Documents\NinjaTrader 8\bin\Custom")
) | Where-Object { $_ -ne $custom -and (Test-Path $_) }
foreach ($sec in $secondary) {
    Write-Host "Secondary tree: $sec"
    $secAddons = Join-Path $sec "AddOns"
    New-Item -ItemType Directory -Path $secAddons -Force | Out-Null
    foreach ($name in $files) {
        $src = $null
        if ($name -eq "Lumina.Fabric.NtBridge.dll") { $src = $bridgeSrc }
        else {
            foreach ($dir in $srcCandidates) {
                $p = Join-Path $dir $name
                if (Test-Path $p) { $src = $p; break }
            }
        }
        if ($src) {
            Copy-OrStage -Src $src -DestDir $sec -Name $name
            Copy-OrStage -Src $src -DestDir $secAddons -Name $name
        }
    }
}

Write-Host ""
Write-Host "Deployed/staged $copied assemblies to:"
Write-Host "  $custom"
Write-Host ""
Write-Host "NEXT STEPS:"
Write-Host "  1. If NT was running: fully EXIT NinjaTrader, re-run this script to promote .dll.new"
Write-Host "  2. Start NT, wait until datafeed Connected"
Write-Host "  3. New -> LUMINA (status). Do NOT use Repair unless you accept NT restart."
Write-Host "  4. Lumina -> Test connection (historical_bars GREEN)"
Write-Host "  Proof: %APPDATA%\LUMINA\fabric-nt-host.log + nt-lifecycle.log"
