# ADR-0022: Meta Self-Eval Strategy Probe

## Status

Accepted (2026-06-27)

## Context

ADR-0021 introduced `BirthMetaController` with rule-based recovery strategy selection. On prolonged velocity stall, the controller still picks **one** strategy without empirically comparing alternatives. Provisional pass remained tied only to `strong_recovery_attempts`, not an explicit “all recovery probes failed” decision.

## Decision

Add a **Strategy Probe** state machine within the birth meta layer:

1. **Trigger** — After prolonged stall (`low_velocity_attempts >= meta_self_eval_min_stall_attempts`) and sufficient strong-recovery attempts, while volume gate is passed.
2. **Probe** — Rotate through a configurable strategy queue (`pattern_inject_aggressive`, `explore_boost`, `reward_shaping_tweak`, `data_expansion`, `intra_ease` [Stage1 only], `explore_reduce`) for `meta_self_eval_rollouts_per_strategy` rollouts each (default 12).
3. **Score** — Per strategy: `velocity_delta = combined_velocity_end - combined_velocity_start`.
4. **Commit** — Highest delta above `meta_self_eval_min_velocity_gain` with `combined_at_end > meta_self_eval_velocity_floor`; tie-break on `combined_at_end`.
5. **Exhausted** — No qualifying winner → `suggest_provisional_pass` (practice mode only; certified remains blocked).

Implementation:

- Pure helpers: [`lumina_core/birth/meta_self_eval.py`](../../lumina_core/birth/meta_self_eval.py)
- Controller API: `maybe_start_self_eval`, `decide_probe_rollout`, `on_probe_rollout_complete`, `decide_committed_rollout`, `evaluate_provisional_fallback`
- Engine gate in `_run_stage_research_loop`: skips stall-driven `decide_review` during PROBING/COMMITTED; progress suffix `· self-eval: probing … (n/N)`
- Config: `birth_v2.curriculum.meta_self_eval_*`; feature flag `meta_self_eval_enabled` (default `true`)

**Invariants:**

- Certified pass thresholds and constitution guard unchanged.
- Provisional pass only when `allow_provisional` and all safeguards pass, including explicit `self_eval_exhausted`.
- Cooldown (`meta_self_eval_cooldown_rollouts`) prevents immediate re-probe after exhaustion.

## Consequences

- Positive: Empirical A/B of recovery levers within a single birth run (no restart).
- Positive: Explicit exhausted → provisional path with structured logging (`birth.meta.self_eval.exhausted`).
- Negative: Additional rollout budget (max ~6 strategies × 12 rollouts); mitigated by cooldown and context-filtered queue.
- Negative: Rule-based probe ordering only; ML strategy ranking deferred.

## Mission alignment

Extreme intellectual honesty: recovery decisions backed by measured velocity delta, not single-shot heuristics. Rigorous testing via `tests/birth/test_meta_self_eval.py`. Radical creativity bounded by constitution and certified-mode safeguards.
