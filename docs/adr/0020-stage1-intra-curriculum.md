# ADR-0020: Stage 1 Intra-Curriculum (Easy→Hard)

## Status

Accepted (2026-06-27)

## Context

Birth Stage 1 filters all trend ticks but mixes them uniformly during rollouts. Weak or marginal trends dominate early learning noise; the agent sees hard examples before mastering strong, persistent trends. Trend enrichment (ADR-0018) already exposes `trend_regime_strength`, `trend_duration_norm`, and `trend_adx_14` on each tick.

## Decision

Add an **autonomous intra-stage curriculum** for `STAGE1_TREND` only:

1. **Difficulty score** — `strength×0.5 + duration×0.3 + adx×0.2` (data-driven percentiles, not fixed USD thresholds).
2. **Pools** — top `intra_easy_percentile` → easy; remainder → hard; tag `_intra_difficulty`.
3. **Sampling** — start at `intra_initial_hard_pct` (default 15% hard); sample proportional easy/hard pool per rollout chunk.
4. **Ramp** — after `intra_easy_stability_window` consecutive chunk winrates on easy ticks ≥ `intra_easy_winrate_target`, increase `hard_pct` by `intra_hard_pct_step` (monotonic, cap `intra_max_hard_pct`).
5. **Checkpoint** — persist `hard_pct`, easy trade counters, and winrate history in `stage_metrics`.
6. **Sim metrics** — `SimRolloutResult.easy_trades` / `easy_wins` from ticks tagged `"easy"`.

Implementation SSOT: [`lumina_core/birth/curriculum.py`](../../lumina_core/birth/curriculum.py). Engine wiring in [`lumina_core/birth/engine.py`](../../lumina_core/birth/engine.py). Config under `birth_v2.curriculum.intra_stage1_*`.

**Invariants:**

- Stage 2+ unchanged (intra gated on `stage == STAGE1_TREND`).
- REAL mode unaffected (birth-only curriculum).
- Thin easy pool fallback when `< 100` ticks (relaxed percentile split).

## Consequences

- Positive: Faster early Stage 1 convergence on high-quality trend samples.
- Positive: Autonomous difficulty ramp without manual threshold tuning per dataset.
- Negative: Small datasets may produce thin pools — fallback split applies.
- Negative: Checkpoint resume must restore `hard_pct` to avoid curriculum reset.

## Related ADRs

- ADR-0014: Birth curriculum stages
- ADR-0018: Trend observation features (difficulty score inputs)
