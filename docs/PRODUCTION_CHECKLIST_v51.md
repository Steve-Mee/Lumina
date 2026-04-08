# PRODUCTION CHECKLIST v51 - Lumina Living Organism

Date: 2026-04-06
Validator: GitHub Copilot (GPT-5.3-Codex)
Mode: Fail-closed assessment

## 1) All Components Status (Green/Red)

| Component | Status | Evidence |
|---|---|---|
| Full test suite (`pytest -v --tb=short --cov`) | GREEN | 252 passed, 2 skipped, coverage plugin active |
| Chaos Engineering suite (`python -m pytest tests/chaos_engineering.py -q`) | GREEN | 21 passed |
| SessionGuard module + CME-first calendar call | GREEN | `session_guard.py` present, `get_calendar("CME")` first with fallback aliases |
| RiskController intraday cooldown + fail-closed session guard | GREEN | `session_cooldown_minutes` + `enforce_session_guard` wired and tested |
| Trade submit SessionGuard gate (`trade_workers.py`) | GREEN | pre-submit block on closed/rollover session |
| Reasoning degrade outside session (`reasoning_service.py`) | GREEN | forces fast-path HOLD outside session |
| Nightly sim calendar-aware behavior (`nightly_infinite_sim.py`) | GREEN | session snapshot + `calendar_blocked` branch |
| Evolution UI (v51 Critical #2 carry-over) | GREEN | tests pass and endpoint/UI integration present |
| Live-sim launcher run (paper 15m) command semantic validity | RED | command executes Streamlit bare-mode warnings; no deterministic trade-loop summary |
| Live-broker mocked launcher run semantic validity | RED | same as above; command accepted but not proving broker execution path |

## 2) BrokerBridge Live Readiness

Status: GREEN (with operational caveats)

Verified:
- Broker abstraction exists and is container-wired.
- `paper` and `live` backends selectable via config/env.
- Submit paths route through broker bridge.
- Tests for broker bridge and routing pass.

Caveats before real-money:
- Validate outbound connectivity + auth against real broker endpoints in a controlled paper account window.
- Add explicit integration smoke command that exercises non-UI runtime loop (not Streamlit app entrypoint).
- Ensure live credential rotation and secret-injection path is documented for deployment.

## 3) Risk Controller + SessionGuard + VaR

Status: GREEN

Implemented and green:
- SessionGuard checks in risk layer and submit boundary.
- Intraday cooldown field and logic integrated.
- Portfolio VaR allocator implemented (historical + parametric) with correlation-aware portfolio guard.
- `max_open_risk_per_instrument` and `max_total_open_risk` enforced.
- VaR telemetry + breach alert integrated in observability.
- Holiday/rollover + correlated MES/NQ spike chaos tests passing.

Enforcement contract:
- Risk enforcement is applied in `check_can_trade(...)` (this is the active pre-submit gate when live rules are enabled).

## 4) Observability Alerts Tested

Status: GREEN

Evidence:
- Observability metrics/alert tests pass in full suite.
- Session/risk related alert pathways exercised via unit and chaos scenarios.

Recommended pre-prod hardening:
- Run one end-to-end webhook test in staging (Slack/Discord/Telegram target) with alert dedupe verification.

## 5) Evolution UI Tested

Status: GREEN

Evidence:
- Streamlit AppTest smoke suite present and passing.
- Backend approve/reject endpoints integrated.
- Observability hooks for approvals/rejections are wired.

## 6) Remaining Gaps for Real-Money Launch

Fail-closed launch decision: NOT READY for real money yet.

Blocking gaps:
1. Launcher command path used in production readiness script currently executes Streamlit UI context in bare mode and does not provide deterministic runtime trade-loop validation output for `--mode/--duration/--broker`.
2. No explicit non-UI CLI smoke command for broker-live mocked execution summary.

Recommended surgical follow-ups:
1. Add/validate a dedicated runtime CLI entrypoint (non-Streamlit) for timed paper/live-mock simulations.
2. Implement VaR limits and add dedicated test coverage + observability metrics.
3. Add production runbook command pair for paper 15m and live-mock 5m that outputs a structured JSON summary.

## 7) Validation Command Outputs

Executed in exact requested order:

1) `pytest -v --tb=short --cov`
- First run: failed due missing `pytest-cov` plugin (`--cov` unrecognized).
- Fix applied: installed `pytest-cov` in workspace venv.
- Re-run: `252 passed, 2 skipped` with coverage report.

2) `python -m pytest tests/chaos_engineering.py -q`
- Result: `21 passed`.

3) `python -m lumina_launcher --mode=paper --duration=15m --broker=paper`
- Result: process starts Streamlit bare-mode path with ScriptRunContext warnings; no deterministic trade-loop summary emitted.
- Fail-closed interpretation: command executed, runtime validation evidence insufficient.

4) `python -m lumina_launcher --mode=paper --duration=5m --broker=live` (mock endpoints set)
- Result: same Streamlit bare-mode behavior; no deterministic broker execution summary emitted.
- Fail-closed interpretation: command executed, live-mock validation evidence insufficient.
