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

## 6. Stage 1 stall abort (certified wall)

1. During `stage1_trend`, if the volume gate is met but EdgeScore hygiene fails (WR below `stage1_winrate_pass_floor`, default 35%; vanity 45% is diagnostic only):
   - Scorecard shows blocker text (e.g. `Hygiene WR 33% (need >=35%)`).
   - When `max_stage_wall_sec` expires (`wall_budget_exhausted`) **or** `certified_stage_stall_wall_sec` plus stagnation rollouts elapse, phase becomes `stage_stalled` (or plateau/swarm escalates first). Soft `explore_boost` alone is not a valid end state.
2. UI recovery panel offers **Retry stage**, **Expand data & retry**, **Wipe & restart**.
3. **Fail if:** birth runs hours past wall budget at sub-hygiene WR without `stage_stalled`, plateau entry, swarm tournament, or blocker HUD.

## 7. Accept criteria

- **Pass:** Birth certificate issued **or** clear abort with `failure_reasons` / `stage_stalled` after configured walls.
- **Pass:** All steps 1–6 observed without silent stalls or misleading UI.
- **Defer production birth** until this shadow run passes on the same data profile you plan to use in production.

## Log markers (grep)

```text
birth.engine.version=BRO-v2
birth.stage.passed
birth.stage.wall_budget_provisional
birth.stage.wall_budget_exhausted
reused_manifest
holdout_preflight_expansion
certificate_failed
stage_stalled
preserve_checkpoint
pass_reason
```

## Related docs

- [Command Deck startup runbook](command-deck-startup-runbook.md)
- [Launcher setup and model management](launcher-setup-and-model-management.md)
- ADR-0011 Tauri lifecycle gate (startup SSOT)

## Shadow validation appendix

**2026-06-11 — dev workspace (`C:/NinjaTraderAI_Bot`) — Closeout PR-W1–W4**

| Step | Result | Evidence |
|------|--------|----------|
| 1 Deploy gate | PASS | `scripts/verify-birth-deploy.ps1`; `GET /api/birth/status` → `engine_version: "BRO-v2"` |
| 2 Stage 2 wall | PASS (automated) | `tests/birth/test_stage2_bounded.py` |
| 3 Crash resume | PASS (automated) | `tests/birth/test_checkpoint_resume.py` |
| 4 OOS cert fail UI | PASS (automated) | `tests/birth/test_certificate_fast_path.py` + endpoint enrichment |
| 5 Recovery paths | PASS (automated) | `test_retry_fast_path_engine`, `birthClient.test.ts` |
| 6 Stage1 stall abort | PASS (automated) | `test_stage1_wall_stagnation_aborts_before_max_rollouts` + checkpoint on stall |

**Closeout additions (PR-W):** terminal status SSOT (`resolve_terminal_birth_status`), checkpoint persist on `stage_stalled`, `compute_stage_blocker` + recovery model tests.

**Operator before REAL birth:** run `.\scripts\verify-birth-deploy.ps1`, then execute steps 1–6 live on your production data profile and append grep transcript below.

```
# Example grep after live shadow:
# birth.engine.version=BRO-v2
# preserve_checkpoint=true
# certificate_remediation
# stage_stalled
# pass_reason
# wall_budget_exhausted
```

## 8. Perfect Birth Phase Success Metrics (KPI Dashboard)

After certificate issuance and during sustained autonomous runs (autonomy loops, recovery, twin gates), track these **measurable success metrics** to decide when Birth Phase is "perfect" and we can graduate to **Phase 2** (advanced wall triggers, dynamic spawning, REAL broker with twin gate).

| Metric (KPI) | Definition / Source | Target (initial) | Min samples / window | How to observe |
|--------------|---------------------|------------------|----------------------|----------------|
| Twin accuracy vs Steve | % agreement: twin recommendation (score >= threshold on features) matches Steve label (APPROVE/VETO) from registry. `compute_steve_agreement_pct` + `monitoring_twin_training.jsonl` (twin_steve_agreement_pct). Complements avg_error. | >= 80% | >=30 labels (rolling) | `python -m lumina_launcher twin metrics`<br>`tail state/monitoring_twin_training.jsonl`<br>`GET /api/monitoring/...` |
| Autonomy (never-stop) recovery success | `autonomous_recovery_rate_pct` = successes/attempts from `WallAdaptationState` + `BirthAutonomyRecoveryMetrics` (via progress/checkpoint/bus). Includes twin-assisted CONTINUE + phoenix + adaptation. | >= 85% | >=8 attempts (recent stages) | Birth progress JSON `autonomous_recovery_rate_pct`<br>`grep autonomous_recovery` logs<br>Bus topic birth.autonomy.recovery.metrics |
| % auto-approved decisions | `autonomy_level_pct` = (auto_approved_total / decisions_total) * 100. From `AutonomySnapshot` / `compute_autonomy_snapshot` on `monitoring_twin_decisions.jsonl` (high-conf >=0.80 + rec + no risk). | >= 60% | >=20 decisions (24h) | `lumina_core/runtime/runtime_twin_oversight`<br>`monitoring_autonomy_metrics.jsonl`<br>oversight_status() |
| Shadow / twin alignment | % cases where twin rec consistent with shadow outcome (pnl>0 implies rec, or evaluate_shadow_promotion verdict). New `record_shadow_twin_alignment_monitoring` + `monitoring_shadow_twin_alignment.jsonl`. | >= 75% | >=5-10 shadow events | `state/monitoring_shadow_twin_alignment.jsonl`<br>Perfect Birth KPIs in /ops-data |
| Supporting (fail-closed) | autonomous_recovery_count rising; human `needs_attention`/TERMINAL_NOTIFY=0 in window; constitution_violations=0 during autonomy; OOS stable vs cert floors. | 0 violations; count ↑ | Sustained period | `lumina_birth_progress.json` (autonomy_*, constitution_violations)<br>certificate + scorecard |

**New JSONL / monitoring files**:
- `state/monitoring_twin_training.jsonl` (now carries twin_steve_agreement_pct)
- `state/monitoring_autonomy_metrics.jsonl`
- `state/monitoring_shadow_twin_alignment.jsonl`

## 9. Declaring Birth Phase "Done" — Move to Phase 2

**Conjunction gate** (ALL must be true for the `perfect_birth_sustained_hours` or equivalent evidence volume):

- Valid `state/lumina_birth_certificate.json` (constitution_violations==0 + meets thresholds + real_data_pct high).
- Twin accuracy vs Steve >= 80% (N>=30 recent Steve labels).
- Autonomous recovery success rate >=85% (min 8 attempts observed, count non-decreasing).
- Auto-approved decisions >=60% (24h, >=20 decisions).
- Shadow/twin alignment >=75%.
- Zero new FATAL constitution violations in the autonomy window.
- No `TERMINAL_NOTIFY_ONLY` (i.e. human gate required) dispatches in last 48h.
- Post-certificate OOS metrics stable (no >~3% degradation on key winrate/sharpe).

**How to declare + unlock Phase 2**:
1. Operator runs the full runbook (steps 1-8) on practice + live data profile.
2. Confirm KPIs via CLI / curl / progress JSON + logs (transcribe).
3. `echo $(date -Iseconds) > state/perfect_birth_complete.flag`
4. (Optional) Set in config or marker: birth perfect complete.
5. **Phase 2 enabled**: advanced/dynamic wall triggers, dynamic organism spawning, REAL broker integration paths with explicit twin gate (still fully subordinated to constitution + shadow aperture + PromotionGate).

**Verification commands**:
```powershell
# Fast SIM Approval Twin validation (shadow mode; no REAL; harness + CLI)
python scripts/validation/run_sim_birth_twin_validation.py --harness-only
# Optional bounded practice birth with Twin bound:
# python scripts/validation/run_sim_birth_twin_validation.py --practice-birth --target-trades 2000 --timeout-sec 900

python -m lumina_launcher twin metrics
python -m lumina_launcher twin review --list-only --limit 5
curl -H "X-API-Key: ..." http://127.0.0.1:8000/api/monitoring/ops-data | jq '.perfect_birth_kpis'
Get-Content state/lumina_birth_progress.json | ConvertFrom-Json | Select autonomy*, oos*, constitution*
grep -iE "(twin.*(agree|accuracy|steve)|autonomous_recovery|shadow.*align|perfect_birth)" logs/lumina_full_log.csv | tail -20
```
See also: `GET /api/birth/status`, maturity milestones (now includes `perfect_birth_autonomy_proven`).

**Log markers (add to previous)**:
```
twin_steve_agreement_pct
autonomous_recovery_rate_pct
autonomy_level_pct
shadow_twin_aligned
perfect_birth
```

Once declared, the organism has proven **Perfect Birth**: high-fidelity Steve twin + reliable never-stop autonomy + coherent shadow layer. Proceed to Phase 2 work.

## Starship Birth (Phase A + B)

Contract SSOT: [starship-birth.md](starship-birth.md) · Seal II: [starship-birth-seal-ii.md](starship-birth-seal-ii.md).

Quick checks during a live shadow run:

1. **Identical-window swarm** — when policy swarm starts, variants share frozen tick windows (progress / logs mention swarm probe then variants; no fresh shuffle each cycle). If windows go missing while active → fail-closed attention (`swarm_frozen_windows_missing`), never a fresh tick pool.
2. **Swarm reject** — no tournament lift → champion restored, `needs_attention` / `swarm_no_tournament_lift` (legacy `swarm_no_edgescore_lift` still recognized); ladder **and** stall remediation must not burn after freeze.
3. **Twin CONTINUE** — only if twin mode is already `full_auto` **and** swarm tournament resolved (commit or accept-champion — not reject alone); constitution still vetoes.
4. **Certificate** — numeric OOS floors unchanged; progress may show `oos_regime_breakdown`; empty claimed regime → `oos_regime_empty`.
5. **Stage 2/3** — EdgeScore criteria ids `range_edgescore` / `mixed_edgescore` (decimal, not vanity %).

## Related docs (updated)

- [starship-birth.md](starship-birth.md) — Phase A+B contract (cert floors frozen, full_auto rules)
- ADR-0031 (approval-twin-event-bus), ADR-0032 (approval-twin-human-replacement)
- LUMINA_BIRTH_ADAPTIVE_WALL_RETRY_DESIGN.md
- maturation_progress.py (milestones)
- Full architecture + AGI_SAFETY (constitution always wins)
