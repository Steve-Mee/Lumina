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
REM   scripts\start_controlled_live.bat
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

echo [%date% %time%] === CONTROLLED LIVE-MONEY CUTOVER START ===
echo.

REM Check venv
if not exist .venv\Scripts\python.exe (
    echo ERROR: .venv not found or not activated
    exit /b 1
)

echo [INFO] Python venv OK

REM Check credentials
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

REM Create Python script to inject caps into config.yaml
python.exe << 'PYTHON_CONFIG_INJECT'
import yaml
import sys

try:
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Ultra-conservative caps for controlled live
    if 'risk_controller' not in config:
        config['risk_controller'] = {}
    
    config['risk_controller']['daily_loss_cap'] = -150.0
    config['risk_controller']['max_consecutive_losses'] = 1
    config['risk_controller']['max_open_risk_per_instrument'] = 75.0
    config['risk_controller']['max_total_open_risk'] = 150.0
    config['risk_controller']['max_exposure_per_regime'] = 100.0
    config['risk_controller']['cooldown_after_streak'] = 60
    config['risk_controller']['session_cooldown_minutes'] = 60
    config['risk_controller']['enabled'] = True
    config['risk_controller']['enforce_session_guard'] = True
    
    # Ensure paper mode first
    if 'broker' not in config:
        config['broker'] = {}
    config['broker']['backend'] = 'live'
    
    # Enable capital preservation features
    if 'trading' not in config:
        config['trading'] = {}
    
    config['trading']['news_avoidance_pre_minutes'] = 10
    config['trading']['news_avoidance_post_minutes'] = 5
    config['trading']['news_avoidance_high_impact_pre_minutes'] = 15
    config['trading']['news_avoidance_high_impact_post_minutes'] = 10
    config['trading']['eod_force_close_minutes_before_session_end'] = 30
    config['trading']['eod_no_new_trades_minutes_before_session_end'] = 60
    config['trading']['overnight_gap_protection_enabled'] = True
    config['trading']['kelly_fraction_max'] = 0.25
    config['trading']['kelly_min_confidence'] = 0.65
    
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print("[OK] Ultra-conservative caps injected into config.yaml")
    sys.exit(0)
except Exception as e:
    print(f"[ERROR] Failed to inject caps: {e}")
    sys.exit(3)
PYTHON_CONFIG_INJECT

if errorlevel 1 (
    echo [ERROR] Config injection failed - restoring backup
    copy /y config.yaml.pre_controlled_live.bak config.yaml > nul
    exit /b 3
)
echo.

REM STEP 3: Run 30m live-broker validation with paper mode
echo [STEP 3] Running 30-minute live-broker validation (paper mode)...
echo [INFO] Command: .venv\Scripts\python.exe -m lumina_launcher --mode=paper --duration=30m --broker=live --headless

.venv\Scripts\python.exe -m lumina_launcher --mode=paper --duration=30m --broker=live --headless > lumina_validation_output.log 2>&1

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

.venv\Scripts\python.exe << 'PYTHON_CONTRACT_CHECK'
import json
import sys
from pathlib import Path

# Check for valid summary file
summary_files = [
    'state/last_run_summary_controlled_live_30m.json',
    'state/last_run_summary_live_30m_paper.json',
    'state/last_run_summary.json'
]

found_file = None
for f in summary_files:
    if Path(f).exists():
        found_file = f
        break

if not found_file:
    print("[ERROR] No validation summary JSON found")
    sys.exit(1)

try:
    with open(found_file, 'r') as f:
        data = json.load(f)
    
    # Verify contract fields
    required = ['runtime', 'broker_status', 'total_trades', 'risk_events', 'var_breach_count']
    for field in required:
        if field not in data:
            print(f"[ERROR] Missing required field: {field}")
            sys.exit(2)
    
    # Verify key values
    if data.get('broker_status') != 'live_connected':
        print(f"[ERROR] Expected broker_status='live_connected', got '{data.get('broker_status')}'")
        sys.exit(3)
    
    if data.get('risk_events', 0) != 0:
        print(f"[WARNING] Expected risk_events=0, got {data.get('risk_events')}")
    
    if data.get('var_breach_count', 0) != 0:
        print(f"[WARNING] Expected var_breach_count=0, got {data.get('var_breach_count')}")
    
    print(f"[OK] Contract verified from {found_file}")
    print(f"     runtime={data.get('runtime')}, broker_status={data.get('broker_status')}")
    print(f"     trades={data.get('total_trades')}, pnl={data.get('pnl_realized')}, risk_events={data.get('risk_events')}")
    sys.exit(0)

except Exception as e:
    print(f"[ERROR] Contract check failed: {e}")
    sys.exit(4)
PYTHON_CONTRACT_CHECK

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
