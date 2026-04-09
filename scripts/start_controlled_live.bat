@echo off
REM ============================================================================
REM start_controlled_live.bat - SIM-First Validation and Real-Money Cutover Script
REM ============================================================================
REM Purpose: Run SIM-first validation by default, with explicit real-money cutover only via --real
REM Method:  30-minute paper validation first, then opt into real-money controls when approved
REM
REM FAIL-CLOSED: All checks must pass or script aborts with error code
REM
REM Usage:
REM   scripts\start_controlled_live.bat --real
REM
REM Contract:
REM   - --real flag is mandatory
REM   - Final 30m SIM validation runs first (fail-closed)
REM   - REAL cutover validation runs only after SIM validation is GREEN
REM
REM Prerequisites:
REM   - .venv activated
REM   - CROSSTRADE_TOKEN set (real credentials)
REM   - CROSSTRADE_ACCOUNT set (PAPER account first)
REM   - config.yaml broker.backend=live (already set)
REM
REM Output:
REM   - Validation JSON: state\last_run_summary_controlled_live_30m.json
REM   - Config backup: config.yaml.pre_controlled_live.bak
REM   - Exit code 0 = ready for real-money, exit code >0 = abort
REM
REM ============================================================================

setlocal enabledelayedexpansion

cd /d "%~dp0\.."

if not /I "%~1"=="--real" (
    echo ERROR: --real flag is required for controlled live cutover
    echo Usage: scripts\start_controlled_live.bat --real
    exit /b 1
)

set RUNTIME_MODE=real
set BROKER_MODE=live

echo [%date% %time%] === CONTROLLED LIVE-MONEY CUTOVER START ===
echo [INFO] Phase mode: !RUNTIME_MODE! (broker=!BROKER_MODE!)
echo.

REM Check venv
if not exist .venv\Scripts\python.exe (
    echo ERROR: .venv not found or not activated
    exit /b 1
)

echo [INFO] Python venv OK

if "!CROSSTRADE_TOKEN!"=="" (
    echo ERROR: CROSSTRADE_TOKEN not set in environment
    exit /b 1
)

if "!CROSSTRADE_ACCOUNT!"=="" (
    echo ERROR: CROSSTRADE_ACCOUNT not set in environment
    exit /b 1
)

echo [INFO] CROSSTRADE credentials present (token=%CROSSTRADE_TOKEN:~0,10%..., account=!CROSSTRADE_ACCOUNT!)
echo.

REM Backup current config
echo [STEP 1] Backing up current config.yaml...
if exist config.yaml (
    copy /y config.yaml config.yaml.pre_controlled_live.bak > nul
    if errorlevel 1 (
        echo ERROR: Failed to backup config.yaml
        exit /b 2
    )
    echo [OK] Backup created: config.yaml.pre_controlled_live.bak
) else (
    echo ERROR: config.yaml not found
    exit /b 1
)
echo.

REM STEP 2: Inject ultra-conservative caps
echo [STEP 2] Injecting ultra-conservative trading caps...
echo [INFO] Daily loss cap: -150 USD
echo [INFO] Max consecutive losses: 1
echo [INFO] Max per-instrument risk: 75 USD
echo [INFO] Max total open risk: 150 USD
echo [INFO] Session cooldown: 60 minutes

REM Inject caps and phase profile via helper script
.venv\Scripts\python.exe scripts\controlled_live_helper.py inject --config config.yaml --mode !RUNTIME_MODE! --broker !BROKER_MODE!

if errorlevel 1 (
    echo [ERROR] Config injection failed - restoring backup
    copy /y config.yaml.pre_controlled_live.bak config.yaml > nul
    exit /b 3
)
echo.

REM STEP 3: Mandatory final 30m SIM validation
echo [STEP 3] Running mandatory final 30-minute SIM validation...
echo [INFO] Command: .venv\Scripts\python.exe -m lumina_launcher --mode=sim --duration=30m --broker=paper --headless

.venv\Scripts\python.exe -m lumina_launcher --mode=sim --duration=30m --broker=paper --headless > lumina_validation_output.log 2>&1

if errorlevel 1 (
    echo [ERROR] Final SIM validation failed - see lumina_validation_output.log
    echo [RESTORE] Restoring original config
    copy /y config.yaml.pre_controlled_live.bak config.yaml > nul
    exit /b 4
)

echo [OK] Final SIM validation completed successfully

echo [INFO] Verifying final SIM validation contract...
.venv\Scripts\python.exe scripts\controlled_live_helper.py contract-check --expected-broker-status paper_ok

if errorlevel 1 (
    echo [ERROR] SIM contract validation failed
    echo [RESTORE] Restoring original config
    copy /y config.yaml.pre_controlled_live.bak config.yaml > nul
    exit /b 5
)

echo [OK] SIM contract validation passed
echo.

REM STEP 4: Run 30m REAL-mode validation
echo [STEP 4] Running 30-minute REAL-mode validation...
echo [INFO] Command: .venv\Scripts\python.exe -m lumina_launcher --mode=!RUNTIME_MODE! --duration=30m --broker=!BROKER_MODE! --headless

.venv\Scripts\python.exe -m lumina_launcher --mode=!RUNTIME_MODE! --duration=30m --broker=!BROKER_MODE! --headless >> lumina_validation_output.log 2>&1

if errorlevel 1 (
    echo [ERROR] REAL-mode validation failed - see lumina_validation_output.log
    echo [RESTORE] Restoring original config
    copy /y config.yaml.pre_controlled_live.bak config.yaml > nul
    exit /b 4
)

echo [OK] REAL-mode validation completed successfully
echo.

REM STEP 5: Verify JSON contracts
echo [STEP 5] Verifying validation JSON contracts...

.venv\Scripts\python.exe scripts\controlled_live_helper.py contract-check --expected-broker-status live_connected

if errorlevel 1 (
    echo [ERROR] REAL contract validation failed
    echo [RESTORE] Restoring original config
    copy /y config.yaml.pre_controlled_live.bak config.yaml > nul
    exit /b 6
)
echo.

REM STEP 6: Summary and next steps
echo [STEP 6] Validation complete - summary:
echo.
echo [SUCCESS] Controlled live-money cutover validation PASSED
echo.
echo Next steps:
echo  1. Review config changes (diffs against .bak file)
echo  2. Verify kill-switch path documented
echo  3. Confirm Ops approval captured
echo  4. When ready: Start production launcher with these caps
echo.
echo Backup config: config.yaml.pre_controlled_live.bak
echo Validation log: lumina_validation_output.log
echo Summary JSON: state\last_run_summary.json
echo.
echo [%date% %time%] === CONTROLLED LIVE-MONEY CUTOVER COMPLETE (SUCCESS) ===
echo.

exit /b 0
