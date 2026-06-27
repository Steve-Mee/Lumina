# ADR-0021: Birth Meta Controller (Learning Observation & Recovery SSOT)

## Status

Accepted (2026-06-27)

## Context

Birth Phase recovery logic was scattered across [`engine.py`](../../lumina_core/birth/engine.py): velocity stall detection, strong recovery mode, adaptation tier ladder (mine at tier ≥1, expand at tier ≥2), stage-specific stagnation counters, and Stage 1 intra-curriculum ramps. Operators lacked a single observable signal for *which* recovery lever was active and why.

ADR-0014 (curriculum), ADR-0019 (reward shaping), and ADR-0020 (intra-curriculum) each added autonomous tuning without a coordinating meta-layer.

## Decision

Introduce **`BirthMetaController`** as the SSOT for birth-only meta-decisions:

1. **Observe** — `LearningSnapshot` from winrate/reward histories, pattern inject yield, buffer size, stall counters.
2. **Decide** — rule-based `RecoveryStrategy` matrix → `MetaActionPlan` (explore boost/reduce, pattern inject, data expansion, reward tweak, intra ease, adaptation retry).
3. **Execute** — [`engine.py`](../../lumina_core/birth/engine.py) applies side-effects (`_mine_and_inject`, `_maybe_expand_data`, rollout params); controller stays pure.

Implementation: [`lumina_core/birth/meta_controller.py`](../../lumina_core/birth/meta_controller.py). Config under `birth_v2.curriculum.meta_controller_*`. Feature flag `meta_controller_enabled` (default `true`) preserves legacy inline path when `false`.

**Invariants:**

- Certified pass thresholds and constitution guard unchanged.
- REAL mode unaffected (birth/sim only).
- Reward shaping tweaks bounded by `meta_max_expectancy_coeff`; reset on improving velocity.
- Checkpoint persists `meta_strategy_history`, inject yield, active reward coeff, explore multiplier, and review trigger in `stage_metrics`.

### Addendum (2026-06-27): Periodic loop integration

The stage research loop (`_run_stage_research_loop`) invokes **`decide_review()`** on a fixed interval (`meta_review_interval_rollouts`, default 5) and on stall/declining signals. Unified hook applies `MetaActionPlan` via `_apply_meta_plan()` with structured `birth.meta.decision` logging and progress message suffix. Exploration decay uses persistent `meta_explore_multiplier` (bounded 0.4–1.0), reset on strong-recovery exit.

## Consequences

- Positive: Transparent recovery rationale in scorecard (`meta_primary_strategy`, `meta_learning_health`, `meta_pattern_quality`).
- Positive: Unit-testable decision matrix without full engine integration.
- Negative: Engine loop still orchestrates I/O — controller does not mine or expand directly.
- Negative: Rule-based v1; no ML strategy selection (explicitly deferred).

## Related ADRs

- ADR-0014: Birth curriculum stages
- ADR-0019: Expectancy reward shaping
- ADR-0020: Stage 1 intra-curriculum
