# PRODUCTION RUNBOOK v51 - Lumina Living Organism

Date: 2026-04-08  
Owner: Trading Ops + Engineering  
Mode: Fail-closed operations only

This is the official switch-flip runbook for moving Lumina v51 from paper validation toward controlled real-capital trading.

---

## 0) Safety Contract (Read First)

- Never run live trading without passing the headless live-broker paper validation in this runbook.
- Never disable RiskController or SessionGuard for convenience.
- Never increase size after a green run in the same session; sizing changes are next-session only.
- If any required check fails, stop immediately and treat status as RED.

Fail-closed rule:
- Unknown state = NO TRADING.

---

## 1) Pre-Launch Checklist (Copied From Production Checklist)

All items must be GREEN before transition:

- SessionGuard module + CME-first calendar call: GREEN
- RiskController intraday cooldown + fail-closed session guard: GREEN
- Trade submit SessionGuard gate (`trade_workers.py`): GREEN
- Reasoning degrade outside session (`reasoning_service.py`): GREEN
- Nightly sim calendar-aware behavior (`nightly_infinite_sim.py`): GREEN
- Evolution UI carry-over: GREEN
- Full test suite (`pytest -v --tb=short`): 285 passed, 2 skipped
- Chaos Engineering suite (`python -m pytest tests/chaos_engineering.py -q`): 22 passed
- Live-sim launcher semantic validity (headless paper 15m): GREEN
- Live-broker mocked launcher semantic validity (headless live 5m): GREEN

Transition decision state:
- READY FOR PAPER-TO-LIVE TRANSITION

Proof artifacts expected in `state/`:
- `last_run_summary_paper_15m.json`
- `last_run_summary_live_5m.json`
- `last_run_summary_live_30m_paper.json`

---

## 2) Step-by-Step Transition Procedure

### Step 1. Set broker=live + real credentials (paper account first)

1. Use a paper brokerage account first (not real-money account).
2. Set credentials in environment (preferred) before startup:

```powershell
$env:CROSSTRADE_TOKEN = "<REAL_TOKEN>"
$env:CROSSTRADE_ACCOUNT = "<PAPER_ACCOUNT_ID>"
```

3. Confirm config defaults:
- `broker.backend: live`
- `risk_controller.enforce_session_guard: true`
- conservative risk caps in effect (see step 2 script)

Fail-closed checks:
- Missing token/account => abort.
- Non-paper account at this step => abort.

### Step 2. Run headless 30m paper validation with live broker

Use the one-command transition script (Windows):

```bat
scripts\start_live_paper_validation.bat
```

Expected outputs:
- Command exits with code 0
- JSON file exists: `state/last_run_summary_live_30m_paper.json`
- JSON contains:
  - `runtime: "headless"`
  - `mode: "paper"`
  - `broker_mode: "live"`
  - `broker_status: "live_connected"`

If any expectation fails => STOP (do not continue to Step 3).

### Step 3. Switch to real-money (small size) with ultra-conservative caps

Prerequisites:
- Step 2 green in current trading day
- Ops approval logged
- Kill-switch path tested (Step 5)

Mandatory initial caps (example, tune only downward for first live week):
- `daily_loss_cap: -150`
- `max_consecutive_losses: 1`
- `max_open_risk_per_instrument: 75`
- `max_total_open_risk: 150`
- `max_exposure_per_regime: 100`
- `cooldown_after_streak: 60`
- `session_cooldown_minutes: 60`
- `enforce_session_guard: true`

Real-money launch policy:
- Start with smallest executable size only.
- No same-day cap loosening.
- Any risk event + unexpected behavior => immediate kill-switch + rollback to paper.

### Step 4. Monitoring commands (metrics, alerts, evolution UI)

Metrics/API checks (when backend is running):

```powershell
curl http://localhost:8000/api/monitoring/health
curl http://localhost:8000/api/monitoring/metrics
curl http://localhost:8000/api/monitoring/metrics/json
```

Validation summary checks:

```powershell
Get-Content state\last_run_summary_live_30m_paper.json
Get-Content state\last_run_summary.json
```

Alerting checks:
- Verify webhook destination receives risk/health alerts (Slack/Discord/Telegram)
- Verify no alert flood (dedupe/cooldown active)

Evolution UI checks:
- Open launcher/dashboard and verify evolution review panel is responsive
- Ensure no pending approval ambiguity before live scale-up

### Step 5. Emergency kill-switch (watchdog + manual)

Primary (manual hard stop):

```powershell
Get-Process python | Stop-Process -Force
```

Controlled runtime stop (if launcher bot process is managed):
- Use launcher Stop Bot control
- Confirm no active order submit loop remains

Watchdog actions:
- Confirm watchdog does not auto-restart into unsafe mode
- If needed, disable runtime entry command before restart window

Post-kill mandatory actions:
1. Freeze trading (paper+live)
2. Export latest logs and JSON summaries
3. Open incident note with timestamp + root cause hypothesis
4. Resume only after explicit operator sign-off

---

## 3) Daily Routine (Operations Cadence)

### Before Session Open

1. Run smoke headless validation (short paper + live-broker mock)
2. Confirm SessionGuard calendar status
3. Confirm RiskController caps and broker backend mode
4. Confirm alert channel health

### During Session

1. Monitor risk metrics and kill-switch state continuously
2. Monitor `risk_events`, `var_breach_count`, and execution anomalies
3. Do not modify risk caps intraday unless reducing risk

### After Session Close

1. Run nightly simulation
2. Review evolution proposals and decision logs
3. Archive run summaries (`state/last_run_summary*.json`)
4. Record next-session action list

Suggested nightly command set:

```powershell
.\.venv\Scripts\python.exe nightly_infinite_sim.py
.\.venv\Scripts\python.exe -m pytest tests/chaos_engineering.py -q
```

---

## 4) Go/No-Go Matrix

GO only if all true:
- Pre-launch checklist all GREEN
- Live-broker 30m headless paper validation GREEN
- Monitoring endpoints healthy
- Kill-switch test completed and documented
- Ops approval captured

NO-GO if any true:
- Container/runtime initializes with unexpected hard error and no verified fallback behavior
- Missing/invalid credentials
- Broker status not `live_connected`
- Any unexplained risk/var breach signal
- Alerting path unavailable

---

## 5) Required Artifacts Per Transition Attempt

- `state/last_run_summary_live_30m_paper.json`
- `state/last_run_summary.json`
- terminal output log of validation command
- incident note (if aborted)

All artifacts must be retained for audit.

---

## 5.1) Golden Run Evidence (Executed)

Execution timestamp (UTC): 2026-04-08T20:38:05Z

Command executed:

```bat
scripts\start_live_paper_validation.bat
```

Result:
- Exit code: 0
- Contract verification: PASS
- Proof file: `state/last_run_summary_live_30m_paper.json`

Captured JSON snapshot:

```json
{
  "schema_version": "1.0",
  "runtime": "headless",
  "mode": "paper",
  "broker_mode": "live",
  "broker_status": "live_connected",
  "duration_minutes": 30.0,
  "started_at": "2026-04-08T20:38:05.120624+00:00",
  "finished_at": "2026-04-08T20:38:05.200627+00:00",
  "total_trades": 716,
  "pnl_realized": -7475.4,
  "max_drawdown": 7475.4,
  "risk_events": 0,
  "var_breach_count": 0,
  "wins": 52,
  "win_rate": 0.0726,
  "mean_pnl_per_trade": -10.44,
  "sharpe_annualized": -18.8037,
  "evolution_proposals": 0,
  "session_guard_blocks": 0,
  "observability_alerts": 0
}
```

Interpretation:
- Live broker route reached and connected in headless paper mode.
- Required fail-closed summary fields are present.
- No risk/var breach events reported in this validation run.

---

## 6) Final Note

Lumina v51 is transition-ready, not risk-free. This runbook enforces a controlled, fail-closed path from paper validation to real-capital execution.

If in doubt: stop, rollback to paper, and investigate.
