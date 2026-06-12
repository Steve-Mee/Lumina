# Start FastAPI backend for local development (Command Deck uses tauri-app separately).
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$env:PYTHONPATH = $RepoRoot
$env:LUMINA_CONFIG = Join-Path $RepoRoot "config.yaml"
Set-Location (Join-Path $RepoRoot "lumina_os")
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
