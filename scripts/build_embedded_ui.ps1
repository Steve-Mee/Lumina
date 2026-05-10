# Bouwt het React monitoring-dashboard voor ingebed gebruik via FastAPI (/ui/).
# Vereist Node.js + npm. Eenmalig na clone of na UI-wijzigingen.

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Push-Location (Join-Path $RepoRoot "frontend")
try {
    npm ci
    npm run build:embedded
    Write-Host "Klaar: statische UI staat in frontend/dist (FastAPI serveert dit op /ui/)."
}
finally {
    Pop-Location
}
