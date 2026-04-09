# RUNBOOK DELTA v52 - SIM vs REAL Safety Split

Date: 2026-04-09  
Owner: Trading Ops + Engineering  
Scope: Delta on top of v51 production runbook

---

## 1) What Changed

### A. Mode-aware sizing (SIM vs REAL)
- SIM now applies aggressive Kelly sizing behavior from config profile.
- REAL keeps conservative Kelly behavior and caps sizing at configured `max_risk_percent`.
- Sizing now uses confidence scaling so low-confidence signals reduce deployed risk.

Operational effect:
- SIM explores faster (larger position sizes, faster learning signal).
- REAL remains capital-preserving (no unconstrained risk expansion).

### B. REAL EOD hard enforcement
- New entries are blocked in the EOD no-new-trades window.
- Open positions are force-closed in the EOD force-close window.
- Runtime loop sets HOLD while EOD force-close window is active.

Operational effect:
- Reduced overnight gap exposure.
- Fewer late-session discretionary entries.

### C. Safety gate tests
- Dedicated marker `safety_gate` added for deploy-critical tests.
- Run command:

```powershell
python -m pytest -m safety_gate -q
```

Current status:
- 4 passed, 287 deselected.

---

## 2) Mission Alignment Impact

### SIM mission: aggressive learning
- Enabled by larger mode-aware sizing and unconstrained exploration path.
- Evolution remains active with high proposal throughput.

### REAL mission: capital preservation only
- Enforced by conservative sizing cap and EOD flatten/no-new-trade controls.
- Session-aware risk behavior is now explicit at both risk-check and runtime execution layers.

---

## 3) Monitoring Checklist (Post-Deploy)

Run after any release touching risk, runtime, or execution:

1. Safety gate tests
```powershell
python -m pytest -m safety_gate -q
```

2. SIM validation (headless)
```powershell
python -m lumina_launcher --headless --mode=sim --duration=30m --broker=paper
```

3. Confirm summary fields in `state/last_run_summary.json`
- `mode == "sim"`
- `evolution_proposals` remains elevated vs non-SIM baseline
- `pnl_realized` trend not regressing sharply vs prior accepted SIM baseline

4. REAL dry validation (paper/live routing path)
```powershell
python -m lumina_launcher --headless --mode=real --duration=5m --broker=live
```

5. Confirm EOD controls in logs (REAL)
- entries blocked in no-new-trade window
- force-close trigger logged in force-close window

---

## 4) Rollback Plan (Fail-Closed)

Use this when regressions appear in execution, risk, or monitoring:

1. Immediate containment
- Switch runtime to paper mode.
- Stop active process if live routing is active.

2. Disable delta behavior via config fallback
- Set conservative mode:
  - top-level `mode: "real"`
  - conservative `real.*` caps preserved

3. Re-run safety gate
```powershell
python -m pytest -m safety_gate -q
```

4. Re-run headless smoke
```powershell
python -m lumina_launcher --headless --mode=paper --duration=15m --broker=paper
```

5. Resume only after GREEN
- No resume on unknown state.
- Unknown state = NO TRADING.

---

## 5) File Map (Delta)

- `lumina_core/engine/lumina_engine.py`
  - mode-aware Kelly sizing + confidence scaling in adaptive qty path.
- `lumina_core/engine/risk_controller.py`
  - REAL EOD no-new-trades + force-close decision helpers.
- `lumina_core/runtime_workers.py`
  - REAL EOD force-close execution and HOLD suppression.
- `tests/engine/test_lumina_engine_suite.py`
  - SIM qty > REAL qty safety test.
- `tests/test_risk_controller.py`
  - EOD no-new-trades + force-close signal tests.
- `tests/test_runtime_workers.py`
  - REAL EOD force-close integration behavior test.
- `pytest.ini`
  - `safety_gate` marker registration.
