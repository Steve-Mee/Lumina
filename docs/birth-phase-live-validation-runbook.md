# Birth Phase — Operator Live Validation Runbook

Shadow birth run on a **SIM or certified workspace** (no REAL orders). Use this checklist before trusting a multi-day birth on production data.

## Prerequisites

- Backend running with `birth.engine.version=BRO-v2` (check startup logs).
- Workspace in **certified** or **practice** mode — never REAL for this runbook.
- Tauri Command Deck open on the Birth Phase screen.
- Optional: `scripts/reset-onboarding-dev.ps1` for a clean dev workspace.

## 1. Preflight gate

1. Start birth from the UI (default target trades).
2. Within the first few minutes, confirm one of:
   - **Preflight OK** — progress shows `ticks_ready` / `historical_loaded` with holdout regime count ≥ 3.
   - **Preflight expansion** — phase `holdout_preflight_expansion` with visible regime/tick counts.
3. **Fail if:** curriculum stage 2 starts without any preflight message, or holdout shows a single regime with no expansion attempt.

## 2. Stage 2 bounded convergence

1. During `stage2_range`, watch the stage scorecard HUD:
   - `stage_wall_remaining_sec` counts down.
   - **Position flat** metric stays in the 30–70% band when range tick count ≥ 50.
   - `stage_range_round_trips` increases when the policy enters and exits on range ticks.
2. If hold/flat ratio stagnates outside the band, confirm `exploration_active` appears after configured stagnation rollouts.
3. **Fail if:** stage 2 runs for hours with no wall countdown or exploration escalation.

## 3. Checkpoint crash test

1. While stage 2 is active (`curriculum_learning`), stop the backend process.
2. Restart backend and resume birth (Continue learning / resume from checkpoint).
3. Confirm within minutes:
   - Same `stage_trades` count as before crash (± one rollout chunk).
   - Same `stage_range_round_trips` / flat metrics restored from checkpoint.
4. **Fail if:** stage trades reset to zero or curriculum restarts at stage 1.

## 4. Force OOS fail (certificate path)

1. Let birth reach certificate evaluation, or use practice thresholds so cert fails (e.g. NEUTRAL-only holdout, Sharpe 0).
2. Confirm UI shows:
   - `failure_reasons` list (Sharpe, winrate, etc.).
   - Remediation bar with actionable recovery — **not** primarily “missing cert”.
3. **Fail if:** UI hides failure reasons or only shows generic “certificate missing”.

## 5. Recovery paths

| Action | Expected behavior |
|--------|-------------------|
| **Continue learning** | Fast-path remediation — no full curriculum restart from stage 1. |
| **Reuse data & retry** | No preflight expansion; **no** `load_historical_ticks` reload when manifest hash matches (check logs: `reused_manifest=True`). |
| **Wipe & restart** | Fresh birth from preflight; checkpoint cleared. |

## 6. Accept criteria

- **Pass:** Birth certificate issued **or** clear abort with `failure_reasons` after max remediation attempts.
- **Pass:** All steps 1–5 observed without silent stalls or misleading UI.
- **Defer production birth** until this shadow run passes on the same data profile you plan to use in production.

## Log markers (grep)

```text
birth.engine.version=BRO-v2
birth.stage.passed
birth.stage.wall_budget_provisional
reused_manifest
holdout_preflight_expansion
certificate_failed
```

## Related docs

- [Command Deck startup runbook](command-deck-startup-runbook.md)
- [Launcher setup and model management](launcher-setup-and-model-management.md)
- ADR-0011 Tauri lifecycle gate (startup SSOT)
