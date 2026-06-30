# ADR-0023: Birth Plateau Evolution Escalator

## Status

Accepted (2026-06-27)

## Context

Certified birth curriculum with `wall_behavior=adaptive` and ADR-0017 never-stop research can grind indefinitely when learning plateaus: volume gate passes, winrate stays below the pass target with flat velocity, meta self-eval exhausts, and forced recoveries reset the stall wall clock without structural change. Large oracle buffers (>80) prevent the legacy terminal-stall predicate (`data_exhausted AND buffer < 80 AND top tier`).

## Decision

Add a **bounded Evolution Escalator** SSOT in [`lumina_core/birth/plateau_escalator.py`](../../lumina_core/birth/plateau_escalator.py):

1. **Plateau enter** — volume gate passed, winrate below pass target minus gap (default 10pp), flat winrate velocity, and (meta self-eval exhausted OR velocity stall attempts OR trades beyond gate multiplier).
2. **Monotonic plateau clock** — `plateau_started_at` never resets on adaptation/tier recovery (distinct from `stage_started_at` display wall).
3. **Cap forced never-stop** — `max_forced_recoveries_per_plateau` (default 6); after cap, invoke escalator instead of another forced recovery.
4. **Evolution ladder** (max 5 steps, then terminal stall):
   - Expand data window
   - Policy rollback to best winrate snapshot
   - Stage1 intra easy-only pool reset
   - Fresh policy (buffer/oracle retained)
   - Terminal `stage_stalled` with `terminal_stall_reason=plateau_evolution_exhausted`
5. **Best policy checkpoint** — save `birth_best_{stage}.zip` on winrate improvement when `plateau_save_best_policy=true`.
6. **Per-step rollout cap** — `plateau_evolution_rollouts_per_step` bounds rollouts during active plateau evolution.

**Invariants:**

- Escalator ≠ graduation — no stage pass without valid `StagePassReceipt`.
- No provisional pass in certified mode.
- Certificate v2 remains sole REAL gate.

Config under `birth_v2.curriculum.plateau_*` and `max_forced_recoveries_per_plateau`. `max_rollouts_per_stage` tuned to 500 (certified still uses `certified_max_rollouts_per_stage` per evolution step).

## Consequences

- Positive: Honest terminal stall with operator playbook instead of silent infinite grind.
- Positive: Structural pivots (data, policy, curriculum sampling) before giving up.
- Negative: Plateau detection may trigger earlier on noisy winrate — tunable via gap and wall sec.
- Negative: Best-policy rollback requires prior improvement snapshot; first rollback step may no-op.

## Related ADRs

- ADR-0017: Birth research oracle (never-stop on first failure)
- ADR-0014: Curriculum OOS gate
- ADR-0020: Stage 1 intra-curriculum (easy-only evolution step)
- ADR-0021: Birth meta controller (self-eval exhausted signal)
