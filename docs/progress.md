# Adaptive Wall Retry — Progress

**Last updated:** 2026-06-25  
**Current phase:** Complete  
**Overall status:** DONE

---

## Completed

### Fase 0 — Tracking setup (2026-06-25)
- Created `docs/plan.md`, `docs/progress.md`, `TODO.md`

### Fase 1 — Config (2026-06-25)
- Added 6 adaptation fields to `BirthCurriculumConfig`
- Added `_coerce_wall_behavior` with fail-closed fallback to `"strict"`

### Fase 2 — Engine (2026-06-25)
- `AdaptationDecision` + `_get_adaptation_decision` module-level functions
- `_try_adaptive_stall_recovery` nested helper with soft reset
- Stall intercepts at both paths (stagnation+wall and force stall)
- `winrate_history` tracking after rollouts; persisted in `stage_metrics`

### Fase 3 — Scorecard (2026-06-25)
- `calculate_simple_slope` + `enrich_adaptation_payload`
- Extended `SCORECARD_PRESERVE_KEYS`

### Fase 4 — Tests (2026-06-25)
- `tests/birth/test_adaptation_decision.py` — 4 unit tests
- Updated stagnation tests with `wall_behavior="strict"` for regression safety
- Added adaptive integration test in `test_stage1_stagnation.py`
- Scorecard + checkpoint resume tests extended
- **27 tests passed**, ruff clean

### Fase 5 — Handoff (2026-06-25)
- Spec checklist verified (see below)
- Implementation summary added

### Elon-Audit Gap Fix (2026-06-25)
- **P0 fixed:** Post-gate `chunk_target` no longer collapses to 1 (`min(remaining,...)` bypass when `stage_trades >= required`)
- **P1 fixed:** Stall split into `_would_certified_stage_stall` (dry-run) + `_finalize_certified_stage_stall` — no false `stage_stalled` progress during auto-recovery
- **P2 fixed:** `tests/birth/test_post_gate_chunk_target.py` proves 386-trade scenario gets full rollout chunk; adaptive test filters post-gate chunks only
- **Audit verdict:** Goal now fully achieved for engine behavior

---

## Spec Checklist (Design v2.1 §6)

- [x] Config fields added and have sensible defaults
- [x] `winrate_history` maintained and persisted in checkpoints
- [x] `_get_adaptation_decision` exists and matches spec
- [x] Stall path calls decision when `wall_behavior == "adaptive"`
- [x] On adaptation: escalation↑, chunk↑, logged, history recorded, loop continues (soft restart)
- [x] After `max_stage_retries` → terminal stall with full history
- [x] `wall_behavior = "strict"` disables feature entirely
- [x] HUD shows volume gate status + trend + last adaptation
- [x] Post-gate chunk_target uses `rollout_chunk_trades` (not capped at 1)
- [x] Adaptation chunk override effective post-gate
- [x] No spurious `stage_stalled` progress write on successful auto-recovery

---

## Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | `continue` not recursive restart | Avoid stack depth; existing loop supports soft reset |
| 2 | Soft reset on adaptation | Keep learned policy/buffer; reset wall timer + stagnation counters |
| 3 | Persist via `stage_metrics` | Minimal diff; backward compatible defaults |
| 4 | Temp `rollout_chunk_trades` override | Spec intent: boost exploration chunk after volume gate |
| 5 | Module-level decision fn | Unit-testable without full engine run |
| 6 | Slope in scorecard.py | Reuse in HUD + tests |
| 7 | Post-gate chunk bypass | `min(remaining,...)` caps at 1 when trades exceed required; use full rollout chunk post-gate |
| 8 | Stall dry-run | Prevent UI flash of `stage_stalled` during auto-recovery |

---

## Implementation Summary (for next agent)

### What was built

Adaptive self-correction for birth certified stage stalls. When a stall is detected and `wall_behavior="adaptive"`, the engine:
1. Computes an `AdaptationDecision` based on winrate trend after volume gate
2. Increases `rollout_chunk_trades` (exploration chunk)
3. Bumps `escalation_level`, logs reason, appends to `adaptation_history`
4. Soft-resets loop state (attempt, stagnation counters, wall timer)
5. Continues the stage loop; after `max_stage_retries` → normal terminal stall

**Gap fix (Elon audit):** Post-volume-gate rollouts now use `rollout_chunk_trades` directly instead of `min(1, rollout_chunk_trades)`. Adaptation overrides (8–25) are effective. Stall detection is dry-run until recovery is exhausted.

### Files changed

| File | Change |
|------|--------|
| `lumina_core/birth/config.py` | 6 config fields + YAML load |
| `lumina_core/birth/engine.py` | Decision logic, recovery, intercepts, history |
| `lumina_core/birth/stage_scorecard.py` | Slope + HUD enrichment |
| `tests/birth/test_adaptation_decision.py` | New unit tests |
| `tests/birth/test_stage1_stagnation.py` | Strict + adaptive tests |
| `tests/birth/test_stage2_bounded.py` | Strict mode on stall test |
| `tests/birth/test_stage_scorecard.py` | Slope + enrichment tests |
| `tests/birth/test_checkpoint_resume.py` | Adaptation field persistence |
| `tests/birth/test_post_gate_chunk_target.py` | Post-gate chunk + dry-run stall tests |

### How to test locally

```powershell
python -m pytest tests/birth/test_post_gate_chunk_target.py tests/birth/test_stage1_stagnation.py tests/birth/test_adaptation_decision.py -q
python -m ruff check lumina_core/birth/engine.py
```

### Config (YAML)

```yaml
birth_v2:
  curriculum:
    adaptation_enabled: true
    wall_behavior: adaptive   # or "strict" to disable
    max_stage_retries: 3
    exploration_chunk_size: 8
    winrate_trend_window: 12
    negative_slope_threshold: -0.005
```

### Known limitations

- Only affects certified birth research loop (not REAL trading)
- Post-gate default chunk = full `rollout_chunk_trades` (250); adaptation lowers to 8–25 on stall retry
- Existing stall tests use `wall_behavior="strict"` to preserve prior behavior assertions

### Tauri HUD (2026-06-25)

- `BirthProgressPayload` + `StageScorecardModel` expose adaptation fields
- `BirthStageScorecard` shows Adaptive recovery panel (volume gate, trend, retries, last adaptation)

### Suggested follow-ups (optional)

- Run full `tests/birth/` suite in CI
- Observe live STAGE1_TREND stall scenario with `wall_behavior: adaptive` in config.yaml
- Consider persisting `adaptation_history` in progress file for UI display on resume
