# ADR-0049: Awakening — eyes open, prefer-better, no substitution

**Status:** Accepted  
**Date:** 2026-09-18  
**Deciders:** LUMINA Engineering (Steve + Grok)  
**Refines:** [ADR-0026](./0026-evolution-proof-gate.md) implementation (floors stay; loopholes close)  
**Relates:** [ADR-0036](./0036-birth-exit-vs-maturation.md), [ADR-0046](./0046-birth-foundation-evolvable-plant.md), [organism-maturation-phases.md](./organism-maturation-phases.md)

## Context

Birth Foundation (ADR-0046) built an evolvable plant. Awakening is the first consciousness of that plant: prefer a better child than frozen π*, perceive regimes, recover without cheating.

The production runner was an evaluator: one 10k PPO shot, WR lift **or** 45% OOS, Twin `samples` dump, and `effective_min_trades = min(500, max(50, n×0.8))`. A live stamp marked Awakening complete on **133** policy closes (+10.3pp lift, OOS 43.6% — 45% not met). Learned still showed `ep_passed: false`. That is not truth-seeking (constitution #3).

Birth already rejected WR 20/35/40% as pass law. Awakening must not reintroduce a WR-only wall or a sample-count Twin.

## Decision

Awakening exit is fail-closed AND. Floors from ADR-0026 stay (lift ≥ 5pp **or** OOS ≥ 45%) but they sit **on top of** the AND, never instead of it.

| Invariant | Law |
|-----------|-----|
| Birth freeze | Receipts, fitness, completed flag, `birth_exit_pi_star.zip` read-only |
| Train A / eval B | Holdout B never enters `learn()` |
| Policy-only skill | WR, lift, mean_r, edge, Sharpe from policy closes only |
| n_B ≥ 500 | Hard. `effective_min_trades` deleted. n < 500 → INCONCLUSIVE, not pass |
| STABLE | Sharpe > −2, DD ≤ 25% of $50k MES 1-lot. REGRESS / INCONCLUSIVE ≠ pass |
| Occupancy | Exam band 25–75% (same plant-flat as Birth S3–S5) |
| Process-R | `median_loss_r` ≤ 1.5 |
| Prefer-better | edge vs first-touch ≥ 0; child mean_r ≥ Birth fitness mean_r; child sha ≠ init sha |
| Twin-watch | Observations of **this** run (`state/awakening_twin_watch.jsonl`). Metrics dump is not proof |
| Recovery | Honest stall→retry without Birth mutation, floor-cut, or `expand_data` escape. Freeze held through ≥1 cycle proves the living clock; a stall is not required to pass |
| Regime | Slices attempted; insufficient tape → INCONCLUSIVE for that slice, never skip |
| Soft-complete | May warn on hub. Must not set `ok=True` |

Geometry BE (~0.46) is HUD skill pressure. WR ≥ BE remains a **Playground** gate (ADR-0046). Do not pull later walls into Awakening.

SSOT: `lumina_core/maturity/awakening/law.py`. Progress: `state/lumina_awakening_progress.json`. A continuum stamp of `awakening` completed that fails this law is healed to incomplete. Birth is not touched.

## Consequences

### Positive

- 133-trade lift cannot complete Awakening.
- Operator sees the same AND the engine uses.
- Birth plant stays the frozen parent.

### Negative

- Honest Awakening takes a longer clock (n_B ≥ 500). That is the point.
- One eval walking holdout B (`tape_exhausted`) is INCONCLUSIVE when n_B < 500. It is not a pass and not a clock stop. Cycles continue the child zip. Wipe is the only return to frozen π*.
- If Birth holdout B is physically too thin for 500 policy closes at the plant's observed frequency, the exam **continues after B** with later OOS of the same fixture physics (never train A, never a Birth-cache write). Cycle 0 evals frozen π* on that same exam so lift is same-tape. AND floors are unchanged.
- Plant FORCE_OPEN / FORCE_EXIT closes are occupancy airframe. Skill (WR, mean_r, Sharpe, edge) is policy-only. Zero plant closes is not a pass law.

## Alternatives considered

1. Keep `effective_min_trades` — rejected; it legalizes n=133 against the 500-trade wish.
2. WR-only pass (lift or 45%) — rejected; Birth already retired WR as pass law.
3. Twin dump `samples ≥ 10` — rejected; not watch of this run.
4. Soft-complete lab stamp — rejected in production.

## Links

- Code: `lumina_core/maturity/awakening/`
- Tests: `tests/maturity/test_awakening_law.py`
- Wipe kind: `awakening_only` (Genesis + Birth kept)
