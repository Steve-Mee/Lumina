@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================================
REM Lumina v51 - One-command live-broker paper validation (fail-closed)
REM Runs: headless, broker=live, mode=paper, duration=30m, ultra-conservative caps
REM Output: state\last_run_summary_live_30m_paper.json
REM ============================================================================

set "ROOT_DIR=%~dp0.."
pushd "%ROOT_DIR%" >nul 2>&1
if errorlevel 1 (
  echo [FATAL] Unable to enter repository root.
  exit /b 1
)

set "PYTHON_EXE=.venv\Scripts\python.exe"
set "CONFIG_PATH=config.yaml"
set "BACKUP_PATH=state\config.live_validation.bak.yaml"
set "SUMMARY_PATH=state\last_run_summary_live_30m_paper.json"

if not exist "%PYTHON_EXE%" (
  echo [FATAL] Python venv executable not found: %PYTHON_EXE%
  popd >nul
  exit /b 1
)

if not exist "%CONFIG_PATH%" (
  echo [FATAL] Missing config file: %CONFIG_PATH%
  popd >nul
  exit /b 1
)

if "%CROSSTRADE_TOKEN%"=="" (
  echo [FATAL] CROSSTRADE_TOKEN is not set. Aborting fail-closed.
  popd >nul
  exit /b 1
)

if "%CROSSTRADE_ACCOUNT%"=="" (
  echo [FATAL] CROSSTRADE_ACCOUNT is not set. Aborting fail-closed.
  popd >nul
  exit /b 1
)

if exist "%BACKUP_PATH%" (
  echo [FATAL] Backup already exists: %BACKUP_PATH%
  echo         Resolve manually before running this script again.
  popd >nul
  exit /b 1
)

copy "%CONFIG_PATH%" "%BACKUP_PATH%" >nul
if errorlevel 1 (
  echo [FATAL] Could not create backup: %BACKUP_PATH%
  popd >nul
  exit /b 1
)

echo [INFO] Applying ultra-conservative fail-closed runtime overrides...
"%PYTHON_EXE%" -c "import pathlib,yaml; p=pathlib.Path('config.yaml'); c=yaml.safe_load(p.read_text(encoding='utf-8')) or {}; c.setdefault('broker', {})['backend']='live'; rc=c.setdefault('risk_controller', {}); rc['daily_loss_cap']=-150.0; rc['max_consecutive_losses']=1; rc['max_open_risk_per_instrument']=75.0; rc['max_total_open_risk']=150.0; rc['max_exposure_per_regime']=100.0; rc['cooldown_after_streak']=60; rc['session_cooldown_minutes']=60; rc['enforce_session_guard']=True; p.write_text(yaml.safe_dump(c, sort_keys=False), encoding='utf-8')"
if errorlevel 1 goto :restore_fail

set "LUMINA_HEADLESS_SUMMARY_PATH=%SUMMARY_PATH%"

echo [INFO] Starting headless validation: mode=paper, broker=live, duration=30m
"%PYTHON_EXE%" -m lumina_launcher --mode=paper --duration=30m --broker=live --headless
set "RUN_EXIT=%ERRORLEVEL%"

set "LUMINA_HEADLESS_SUMMARY_PATH="

echo [INFO] Restoring original config.yaml
copy /Y "%BACKUP_PATH%" "%CONFIG_PATH%" >nul
if errorlevel 1 (
  echo [FATAL] Failed to restore config.yaml from backup. Manual intervention required.
  popd >nul
  exit /b 2
)
del /Q "%BACKUP_PATH%" >nul 2>&1

if not "%RUN_EXIT%"=="0" (
  echo [FATAL] Headless validation command failed with exit code %RUN_EXIT%.
  popd >nul
  exit /b %RUN_EXIT%
)

if not exist "%SUMMARY_PATH%" (
  echo [FATAL] Expected summary file missing: %SUMMARY_PATH%
  popd >nul
  exit /b 3
)

echo [INFO] Verifying summary contract...
"%PYTHON_EXE%" -c "import json, pathlib, sys; p=pathlib.Path('state/last_run_summary_live_30m_paper.json'); s=json.loads(p.read_text(encoding='utf-8')); req=['runtime','mode','broker_mode','broker_status','total_trades','risk_events','var_breach_count']; miss=[k for k in req if k not in s]; ok=not miss and s['runtime']=='headless' and s['mode']=='paper' and s['broker_mode']=='live' and str(s['broker_status']).lower()=='live_connected'; print(json.dumps(s, indent=2)); sys.exit(0 if ok else 4)"
if errorlevel 1 (
  echo [FATAL] Summary verification failed. Treat as NO-GO.
  popd >nul
  exit /b 4
)

echo [SUCCESS] Live-broker paper validation complete. Proof: %SUMMARY_PATH%
popd >nul
exit /b 0

:restore_fail
set "PATCH_EXIT=%ERRORLEVEL%"
echo [FATAL] Could not apply config overrides. Restoring original config and aborting.
copy /Y "%BACKUP_PATH%" "%CONFIG_PATH%" >nul 2>&1
del /Q "%BACKUP_PATH%" >nul 2>&1
popd >nul
exit /b %PATCH_EXIT%
