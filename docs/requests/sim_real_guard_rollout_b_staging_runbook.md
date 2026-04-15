# SIM_REAL_GUARD Rollout B - Staging Parallel Run Runbook

Date: 2026-04-15
Owner: Trading Ops + Engineering
Scope: Private dark-launch staging run for `sim_real_guard`
Status: Execution-ready

## Objective

Validate that `sim_real_guard` behaves like REAL for runtime guards while still using SIM account intent, before enabling any controlled pilot.

This runbook is for Rollout B only:
- control lane: `sim`
- candidate lane: `sim_real_guard`

The goal is not PnL optimization. The goal is parity evidence.

## Hard Constraints

- `sim_real_guard` is still dark-launched and must not be exposed in the public launcher mode selector.
- The candidate lane must set `ENABLE_SIM_REAL_GUARD=true`.
- The candidate lane must set `TRADERLEAGUE_ACCOUNT_MODE=sim`.
- Both lanes must route through `broker.backend=live`.
- Both lanes must run against SIM brokerage intent only during Rollout B.
- Do not run both lanes from the same mutable `state/` and `logs/` directory.

## Required Topology

Use two isolated working directories on the same machine or two separate staging machines.

Recommended names:
- `C:\Lumina-Staging-SIM-Control`
- `C:\Lumina-Staging-SIM-Real-Guard`

Minimum isolation requirement:
- separate workspace directory
- separate `state/`
- separate `logs/`
- separate `TRADE_RECONCILER_STATUS_FILE`
- separate `TRADE_RECONCILER_AUDIT_LOG`

If you cannot isolate the directories, do not run Rollout B.

## Environment Setup

### Control lane: `sim`

PowerShell example:

```powershell
$env:CROSSTRADE_TOKEN = "<staging-token>"
$env:CROSSTRADE_ACCOUNT = "<sim-account-id>"
$env:TRADE_MODE = "sim"
$env:BROKER_BACKEND = "live"
$env:TRADERLEAGUE_ACCOUNT_MODE = "sim"
$env:ENABLE_SIM_REAL_GUARD = "false"
$env:TRADE_RECONCILER_STATUS_FILE = "state/trade_reconciler_status_sim.json"
$env:TRADE_RECONCILER_AUDIT_LOG = "logs/trade_fill_audit_sim.jsonl"
```

### Candidate lane: `sim_real_guard`

PowerShell example:

```powershell
$env:CROSSTRADE_TOKEN = "<staging-token>"
$env:CROSSTRADE_ACCOUNT = "<sim-account-id>"
$env:TRADE_MODE = "sim_real_guard"
$env:BROKER_BACKEND = "live"
$env:TRADERLEAGUE_ACCOUNT_MODE = "sim"
$env:ENABLE_SIM_REAL_GUARD = "true"
$env:TRADE_RECONCILER_STATUS_FILE = "state/trade_reconciler_status_sim_real_guard.json"
$env:TRADE_RECONCILER_AUDIT_LOG = "logs/trade_fill_audit_sim_real_guard.jsonl"
```

## Private Start Path

Because `sim_real_guard` is intentionally not public in the launcher selector yet, use the private runtime start path.

Start command in each isolated workspace:

```powershell
c:/NinjaTraderAI_Bot/.venv/Scripts/python.exe lumina_v45.1.1.py
```

If the staging workspace lives at another path, use that workspace's venv and runtime entry.

## Fully automated window runner

For no-touch evidence collection, use the automated rollout runner instead of starting both lanes manually.

Example:

```powershell
c:/NinjaTraderAI_Bot/.venv/Scripts/python.exe scripts/validation/run_sim_real_guard_rollout_b.py `
  --control-root C:/Lumina-Staging-SIM-Control `
  --candidate-root C:/Lumina-Staging-SIM-Real-Guard `
  --window-label D1_09-30_10-00 `
  --duration 30m `
  --broker live `
  --crosstrade-token <staging-token> `
  --crosstrade-account <sim-account-id>
```

This automation does all of the following:
- launches both lanes in parallel
- forces the required env mapping for each lane
- collects summaries, metrics, reconciler status, audit logs, and advisory evidence
- writes a per-window parity report
- appends to cumulative parity history
- updates a rolling `rollout_b_decision.json`

Generated artifacts:
- `state/validation/sim_real_guard_rollout_b/parity_window_*.json`
- `state/validation/sim_real_guard_rollout_b/parity_history.jsonl`
- `state/validation/sim_real_guard_rollout_b/rollout_b_decision.json`

## Windows Task Scheduler bootstrap

After the staging roots exist and credentials are provisioned once, you can register all 15 windows in one command.

If the staging roots do not exist yet, bootstrap both isolated workspaces and optionally register the tasks in one step:

```powershell
.\scripts\validation\bootstrap_sim_real_guard_rollout_b.ps1 `
  -ControlRoot C:\Lumina-Staging-SIM-Control `
  -CandidateRoot C:\Lumina-Staging-SIM-Real-Guard `
  -CrossTradeToken <staging-token> `
  -CrossTradeAccount <sim-account-id> `
  -StartDate 2026-04-16 `
  -TradingDays 5 `
  -RegisterTasks `
  -Force
```

What this bootstrap now automates:
- creates the two isolated rollout workspaces
- copies the current codebase without sharing mutable `state/` or `logs/`
- writes mode-correct `.env` files for control and candidate lanes
- pins `ALLOW_SIM_REAL_GUARD_REAL_PROMOTION=false`
- reuses the main workspace Python executable for scheduled execution
- optionally registers the full 15-window schedule immediately

```powershell
.\scripts\validation\register_sim_real_guard_rollout_b_tasks.ps1 `
  -ControlRoot C:\Lumina-Staging-SIM-Control `
  -CandidateRoot C:\Lumina-Staging-SIM-Real-Guard `
  -CrossTradeToken <staging-token> `
  -CrossTradeAccount <sim-account-id> `
  -StartDate 2026-04-16 `
  -TradingDays 5 `
  -Force
```

This registers one scheduled task per window and uses `run_rollout_b_window.ps1` as the execution wrapper.

To remove the registered rollout tasks:

```powershell
.\scripts\validation\unregister_sim_real_guard_rollout_b_tasks.ps1
```

Resulting automation model:
- one-time bootstrap: credentials + staging roots + task registration
- no per-window operator action required
- automatic parity evidence and rolling decision artifacts after every window

## Automated release gate report

After rollout windows complete, build the promotion-readiness report automatically:

```powershell
c:/NinjaTraderAI_Bot/.venv/Scripts/python.exe scripts/validation/build_sim_real_guard_release_gate.py `
  --repo-root C:/NinjaTraderAI_Bot `
  --candidate-root C:/Lumina-Staging-SIM-Real-Guard
```

Generated artifact:
- `state/validation/sim_real_guard_rollout_b/release_gate_report.json`

This report automatically evaluates:
- acceptance criteria tied to regression coverage and rollout evidence
- longest green-window streak
- timeout/mismatch SLO status
- unresolved critical incidents without RCA
- sign-off count required before promotion

Controlled-pilot implication:
- `ENABLE_SIM_REAL_GUARD_PILOT=true` exposes `sim_real_guard` in the launcher selector for limited pilot machines
- `ENABLE_SIM_REAL_GUARD_PUBLIC=true` is reserved for public launcher exposure later
- `ALLOW_SIM_REAL_GUARD_REAL_PROMOTION=false` remains the default gate until the release report and sign-off pass

Exit codes:
- `0`: current window passed (`GO_WINDOW`)
- `2`: current window failed (`NO_GO_WINDOW`)

## Daily Execution Windows

Run both lanes on identical market windows for 5 trading days.

Required windows per day:
1. `09:30-10:00` local exchange session open behavior
2. `12:00-12:30` mid-session steady-state behavior
3. `15:20-15:55` late-session and EOD enforcement behavior

Do not change instrument, risk profile, or environment variables intraday.

Recommended fixed instrument for all 5 days:
- `MES JUN26`

## Day-by-Day Plan

### Day 1 - Startup and session-gate validation

Objective:
- prove startup contract correctness
- prove session-related guard behavior is stable

Must verify:
- candidate lane starts only when `ENABLE_SIM_REAL_GUARD=true`
- candidate lane fails closed when `TRADERLEAGUE_ACCOUNT_MODE != sim`
- both lanes reach healthy runtime
- no unexpected `session_guard_unavailable` or `session_guard_check_failed`

Acceptance thresholds:
- startup mismatches: `0`
- critical startup fail-closed incidents after final config fix: `0`
- session-related unknown-state errors: `0`

### Day 2 - Risk advisory vs strict block mapping

Objective:
- prove that `sim` advisory events map cleanly to `sim_real_guard` risk blocks

Must verify:
- every candidate risk block reason has a corresponding advisory reason in control lane for the same window
- candidate lane blocks on risk where control lane logs advisory only

Acceptance thresholds:
- unmatched candidate risk block reasons: `0`
- difference between candidate risk-block count and control advisory count for the same reason: `<= 1`
- any unexplained block reason category: `0`

### Day 3 - Reconciliation quality

Objective:
- validate reconciler stability and settlement evidence quality in `sim_real_guard`

Must verify:
- `pending_count` returns to `0` after closes
- audit log contains `pending_close`, `fill_received`, and `reconciled`
- `last_error` stays empty during stable feed conditions

Acceptance thresholds:
- `pending_count > 0` longer than 60 seconds after a close: `0`
- `timeout_snapshot` ratio: `<= 2%` of reconciled closes
- websocket/polling hard error loops lasting more than 60 seconds: `0`

### Day 4 - EOD enforcement

Objective:
- validate `sim_real_guard` late-session behavior

Must verify:
- candidate lane blocks late entries in no-new-trades window
- candidate lane force-closes open positions in EOD force-close window
- control lane does not emit EOD force-close behavior

Acceptance thresholds:
- `lumina_mode_eod_force_close_total{mode="sim_real_guard"}` outside EOD windows: `0`
- missing force-close while candidate has an open position inside EOD window: `0`
- unexpected force-close in control lane: `0`

### Day 5 - Consolidated parity decision

Objective:
- produce promotion-ready parity evidence package

Must verify:
- all prior day criteria remain green
- no drift toward unknown or degraded guard behavior
- operator review concludes the candidate lane is predictable and fail-closed

Acceptance thresholds:
- unresolved incidents carried into Day 5: `0`
- missing evidence artifacts: `0`
- operator sign-off count: `2` required

## Evidence to Collect Per Window

Collect the following after each window for both lanes.

### Control lane
- runtime log excerpt
- advisory risk lines (`RISK_ADVISORY`)
- final position state

### Candidate lane
- runtime log excerpt
- `state/trade_reconciler_status_*.json`
- `logs/trade_fill_audit_*.jsonl`
- observability snapshot or metrics scrape showing:
  - `lumina_mode_guard_block_total`
  - `lumina_mode_eod_force_close_total`
  - `lumina_mode_parity_drift_total`

## Required Daily Summary Table

Use this exact structure in the daily ops note.

| Day | Window | Control advisory count | Candidate guard blocks | Candidate timeout ratio | Candidate p95 fill latency ms | Candidate EOD force-close count | Result |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | 09:30-10:00 |  |  |  |  |  |  |
| 1 | 12:00-12:30 |  |  |  |  |  |  |
| 1 | 15:20-15:55 |  |  |  |  |  |  |

Repeat for Days 2 through 5.

## Exact Promotion Criteria From Rollout B To Rollout C

Rollout B passes only if all are true:

1. Session-related candidate block reasons are stable and explainable across all 5 days.
2. Candidate risk-block reasons always map to an advisory or equivalent control signal for the same window.
3. `timeout_snapshot` ratio stays at or below `2%` across the full 5-day sample.
4. Candidate `p95 fill_latency_ms` stays at or below `1500 ms` and does not exceed control lane by more than `25%` over the same window.
5. Candidate `lumina_mode_eod_force_close_total` increments only in true EOD windows.
6. No critical fail-closed incident remains without RCA.
7. Two operators sign the final parity report.

If any of the above fails, Rollout B is NO-GO.

## Immediate Stop Criteria

Stop the candidate lane immediately if any of the following occurs:

1. `TRADERLEAGUE_ACCOUNT_MODE` mismatch is detected after startup.
2. `session_guard_unavailable` or `risk_controller not available` appears in a live candidate session.
3. `pending_count` exceeds `3` for more than `5 minutes`.
4. `last_error` remains non-empty for more than `60 seconds` during active feed conditions.
5. Any force-close occurs outside the defined EOD windows.

## Rollback

If Rollout B is stopped:

1. Stop candidate lane.
2. Remove or unset `ENABLE_SIM_REAL_GUARD`.
3. Reset `TRADE_MODE=sim` in the candidate workspace.
4. Archive candidate evidence under a dated folder in `journal/reports/`.
5. Do not resume until RCA is written and reviewed.

## Deliverables At End Of Day 5

- 5 daily summary tables
- consolidated parity report
- archived candidate audit logs
- archived reconciler status snapshots
- operator sign-off record

When the automated runner is used for every window, the consolidated parity evidence is already available in `rollout_b_decision.json` and `parity_history.jsonl`.

## Decision Output

At the end of Rollout B, record exactly one of these decisions:

- `GO_TO_ROLLOUT_C`
- `REPEAT_ROLLOUT_B`
- `ROLLBACK_TO_SIM_ONLY`