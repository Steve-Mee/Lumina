# ADR-0050: Playground — first contact, crawl in NT SIM, no stamps

**Status:** Accepted  
**Date:** 2026-09-19  
**Deciders:** LUMINA Engineering (Steve + Grok)  
**Refines:** [organism-maturation-phases.md](./organism-maturation-phases.md), [ADR-0046](./0046-birth-foundation-evolvable-plant.md) relocated profit gate, [ADR-0049](./0049-awakening-eyes-open.md) AND-pattern  
**Relates:** [ADR-0027](./0027-lumina-maturation-ladder.md), [ADR-0036](./0036-birth-exit-vs-maturation.md)

## Context

Awakening (ADR-0049) opens the plant's eyes on historical holdout B. Playground is the first step **in the world**: NinjaTrader SIM, fictional capital, real order path.

The production runner was a one-shot evaluator: stamp `deck_unlocked` on start, accept `state/first_sim_order.json` or a `probe_ok` OR, grade economic viability on **Birth** fitness with `breakeven_wr=None`, and allow `playground_eval_ok` soft-complete. That is not first contact. A JSON file is not a fill. Birth tape is not SIM tape. One fill is not a crawl.

Geometry BE (~0.46) and mean R ≥ 0 were relocated out of Birth on purpose (ADR-0046). They must live here as fail-closed AND, on the playground SIM tape, policy-only.

## Decision

Playground exit is fail-closed AND. Soft-complete may warn on the hub. It must not set `ok=True`.

| Invariant | Law |
|-----------|-----|
| Entry | Awakening completed per ADR-0049. Birth freeze intact. Policy = awakening child SHA, not frozen Birth π* |
| Habitat | Command Deck + NT SIM. Mode ∈ {`sim`, `sim_real_guard`}. REAL = halt |
| Envelope | Operator-sealed SIM risk envelope. Missing file is **unsealed** (fail-closed). Legacy “missing ⇒ sealed” does not pass Playground |
| Deck live | Operator opened the deck. Runner start is not `deck_unlocked` |
| First fill | Venue fill via order path: `order_id`, price, qty, instrument, SIM mode, timestamp. JSON / health / milestone-without-fill do not count |
| n_P ≥ 150 | Policy-only SIM **closes**. Below 150 = INCONCLUSIVE, never pass. Same skill-clock floor as Birth `POLICY_EDGE_MIN_TRADES`. No `effective_min` |
| Policy-only | WR, mean R, BE comparison from policy closes. Plant FORCE_OPEN / FORCE_EXIT = airframe |
| Occupancy | Exam band 25–75% plant-flat (Birth S3–S5 / Awakening) |
| Process-R | `median_loss_r` ≤ 1.5 on policy losses. No policy closes → missing, not 0 |
| Economic viability | skill WR ≥ **live geometry BE** (same `birth_trade_geometry` physics on this tape) **and** mean R ≥ 0. Birth fitness is HUD baseline, never pass |
| Envelope breach | Daily kill / open-risk of the seal not violated |
| Soft-complete | Must not set `ok=True` |
| `playground_require_first_order` | Inert. Fill is law, not a slider |

Clock stays open until AND, operator stop, or 3 stall retries (NT down, occupancy crash <0.25, n_P not increasing). No `expand_data`. No second `learn()` on historical A/B. Wipe playground does not touch Genesis, Birth, Awakening, or frozen π*.

**Not in this AND:** Sharpe 0.20 / DD 12% (Apprenticeship), cert OOS 48/0.35/8% (Proving Ground), Twin-watch, WR-only, a single fill.

SSOT: `lumina_core/maturity/playground/law.py`. Progress: `state/lumina_playground_progress.json`. Tape: `state/lumina_playground_tape.jsonl`. `evaluate_exit_proofs("playground")` delegates to `evaluate_playground_exit`. A continuum stamp that fails this law is healed to incomplete.

## Consequences

### Positive

- JSON first-order and Birth-fitness cannot complete Playground.
- Operator HUD can paint the same AND the engine uses.
- Awakening child is the crawler; Birth plant stays frozen.

### Negative

- Honest Playground needs a living NT SIM session (n_P ≥ 150). That is the point.
- Envelope must be explicitly sealed; legacy missing-file-as-sealed is not a pass.

## Alternatives considered

1. Keep first-order JSON / probe OR — rejected; not a venue fill.
2. Grade WR≥BE on Birth fitness — rejected; wrong tape.
3. Pass on envelope + one fill — rejected; crawl is a skill sample, 150 is already law.
4. Soft-complete lab stamp — rejected in production (same as ADR-0049).
5. Pull Sharpe/DD or cert OOS into Playground — rejected; those walls have homes.

## Links

- Code: `lumina_core/maturity/playground/`
- Tests: `tests/maturity/test_playground_law.py`
- Economic kernel: `post_birth_skill_gates.economic_viability`
