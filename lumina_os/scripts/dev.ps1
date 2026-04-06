param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("backend", "dashboard", "seed", "clear", "test")]
    [string]$Action
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

function Get-PythonCommand {
    $candidates = @(
        (Join-Path $root ".venv\Scripts\python.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return "python"
    }

    throw "Geen Python interpreter gevonden. Activeer een venv of installeer Python."
}

$python = Get-PythonCommand
Set-Location $root

switch ($Action) {
    "backend" {
        & $python -m uvicorn backend.app:app --reload --port 8000
        break
    }
    "dashboard" {
        & $python -m streamlit run frontend/dashboard.py
        break
    }
    "seed" {
        & $python scripts/seed_demo_data.py
        break
    }
    "clear" {
        & $python scripts/seed_demo_data.py --clear
        break
    }
    "test" {
        & $python -m pytest -q tests/test_api.py
        break
    }
}
