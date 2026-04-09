@echo off
REM ============================================================================
REM start_controlled_live.bat - Ultra-Conservative Real-Money Cutover Script
REM ============================================================================
REM Purpose: Bridge from paper validation to controlled real-money trading
REM Method:  30-minute live-broker paper validation first, then switch caps down
REM
REM FAIL-CLOSED: All checks must pass or script aborts with error code
REM
REM Usage:
REM   scripts\start_controlled_live.bat          (default: SIM learning phase)
REM   scripts\start_controlled_live.bat --real   (explicit real-money phase)
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

set RUNTIME_MODE=sim
set BROKER_MODE=paper
if /I "%~1"=="--real" (
    set RUNTIME_MODE=real
    set BROKER_MODE=live
)

echo [%date% %time%] === CONTROLLED LIVE-MONEY CUTOVER START ===
echo [INFO] Phase mode: !RUNTIME_MODE! (broker=!BROKER_MODE!)
echo.

REM Check venv
if not exist .venv\Scripts\python.exe (
    echo ERROR: .venv not found or not activated
    exit /b 1
)

echo [INFO] Python venv OK

REM Check credentials only for explicit real-money phase
if /I "!RUNTIME_MODE!"=="real" (
    if "!CROSSTRADE_TOKEN!"=="" (
        echo ERROR: CROSSTRADE_TOKEN not set in environment
        exit /b 1
    )

    if "!CROSSTRADE_ACCOUNT!"=="" (
        echo ERROR: CROSSTRADE_ACCOUNT not set in environment
        exit /b 1
    )

    echo [INFO] CROSSTRADE credentials present (token=%CROSSTRADE_TOKEN:~0,10%..., account=!CROSSTRADE_ACCOUNT!)
) else (
    echo [INFO] SIM mode selected - live credentials not required
)
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

REM STEP 3: Run 30m live-broker validation with paper mode
echo [STEP 3] Running 30-minute validation in !RUNTIME_MODE! mode...
echo [INFO] Command: .venv\Scripts\python.exe -m lumina_launcher --mode=!RUNTIME_MODE! --duration=30m --broker=!BROKER_MODE! --headless

.venv\Scripts\python.exe -m lumina_launcher --mode=!RUNTIME_MODE! --duration=30m --broker=!BROKER_MODE! --headless > lumina_validation_output.log 2>&1

if errorlevel 1 (
    echo [ERROR] Validation failed - see lumina_validation_output.log
    echo [RESTORE] Restoring original config
    copy /y config.yaml.pre_controlled_live.bak config.yaml > nul
    exit /b 4
)

echo [OK] Validation completed successfully
echo.

REM STEP 4: Verify JSON contract
echo [STEP 4] Verifying validation JSON contract...

set EXPECTED_BROKER_STATUS=paper_ok
if /I "!BROKER_MODE!"=="live" (
    set EXPECTED_BROKER_STATUS=live_connected
)

.venv\Scripts\python.exe scripts\controlled_live_helper.py contract-check --expected-broker-status !EXPECTED_BROKER_STATUS!

if errorlevel 1 (
    echo [ERROR] Contract validation failed
    echo [RESTORE] Restoring original config
    copy /y config.yaml.pre_controlled_live.bak config.yaml > nul
    exit /b 5
)
echo.

REM STEP 5: Summary and next steps
echo [STEP 5] Validation complete - summary:
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
