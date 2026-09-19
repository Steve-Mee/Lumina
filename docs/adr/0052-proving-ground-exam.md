# ADR-0052: Proving Ground — driving test before capital, no stamps

**Status:** Accepted  
**Date:** 2026-09-19  
**Deciders:** LUMINA Engineering (Steve + Grok)  
**Refines:** [organism-maturation-phases.md](./organism-maturation-phases.md), [ADR-0007](./0007-promotion-gate-real-mode.md), [ADR-0013](./0013-birth-certificate-v2.md) cert walls relocated by [ADR-0046](./0046-birth-foundation-evolvable-plant.md)  
**Relates:** [ADR-0049](./0049-awakening-eyes-open.md), [ADR-0050](./0050-playground-first-contact.md), [ADR-0051](./0051-apprenticeship-walk.md), [ADR-0002](./0002-shadow-deployment-human-approval.md), [ADR-0027](./0027-lumina-maturation-ladder.md)

## Context

Apprenticeship (ADR-0051) is the walk: five consecutive `sim_real_guard` session days on fictional capital. Proving Ground is the next organ: the **driving test before money**.

The production runner was a one-shot evaluator. Exit was `promotion_gate_passed` **or** `shadow_validation_passed`. Soft-complete (`proving_eval_ok`) could set `ok=True`. Cert walls were read from `state/lumina_birth_certificate.json`. The runner scanned `promotion_gate_audit.jsonl` for any `passed`/`promoted`/`shadow_passed` row and never called `PromotionGate.evaluate()` on this run. Sample floor 30 is noise against a 48% OOS wall. Incomplete was marked failed.

A Birth certificate is not this exam. An old audit line is not this shadow. Human `approve-real` is REAL, not Proving Ground.

## Decision

Proving Ground exit is fail-closed AND. Soft-complete may warn on the hub. It must not set `ok=True`.

| Invariant | Law |
|-----------|-----|
| Entry | Apprenticeship completed per ADR-0051. Birth freeze intact. Policy SHA = apprenticeship child, ≠ Birth π* |
| Habitat | NT SIM. Mode ∈ {`sim`, `sim_real_guard`}. REAL = halt. Shadow places no live orders |
| Envelope | Operator-sealed SIM envelope. Missing file = unsealed. Breach = fail |
| n_G ≥ 150 | Policy-only SIM **closes on the proving-ground tape**. Playground / apprenticeship / Birth tapes do not count. Below 150 = INCONCLUSIVE |
| Policy-only | WR, Sharpe, DD, process-R from policy closes. Plant FORCE_* = airframe |
| Occupancy | Exam band 25–75% plant-flat |
| Process-R | `median_loss_r` ≤ 1.5. No policy closes → missing, not 0 |
| Cert walls | OOS WR ≥ 0.48 **and** Sharpe ≥ 0.35 **and** DD ≤ 8% of $50k MES 1-lot on **this** exam. Birth certificate JSON is never pass |
| Cert source | Eval-only purged folds of the frozen child (no `learn()`) **and** the proving tape. Awakening holdout B alone is the same exam twice. Combinations < 5 = INCONCLUSIVE |
| Shadow | This clock: production-like quotes, orderpath SIM fills, fill-rate + slippage vs backtest. Foreign `passed=true` audit rows do not count |
| PromotionGate | `PromotionGate.evaluate(child_sha, evidence)` — all four criteria AND. Missing evidence = reject. No sample fabrication (`[baseline]*n`, one scalar) |
| Constitution 0 | risk_events=0, var_breach=0, envelope intact, never REAL |
| Recovery | Crash / NT down / occupancy <0.25 → resume the **same** tape. No wipe, no `expand_data`, no floor-cut. `recovery_ok` after freeze held through ≥1 exam cycle |
| Soft-complete | Must not set `ok=True` |
| Clock | Open until AND, operator stop, or 3 stall retries. Incomplete ≠ failed |
| Human approve-real | **Not in this AND.** REAL phase |

`proving_require_promotion_or_shadow` is inert. The law is AND, not an OR slider.

`shadow_validation_passed` / `promotion_gate_passed` may fire **only as a consequence** of this AND.

**Not in this AND:** Sharpe 0.20 / DD 12% / 5 green days (Apprenticeship), WR≥BE (Playground), Twin-watch, n_B, Evolution Proof lift, Birth fitness, human approval.

SSOT: `lumina_core/maturity/proving_ground/law.py`. Progress: `state/lumina_proving_ground_progress.json`. Tape: `state/lumina_proving_ground_tape.jsonl`. `evaluate_exit_proofs("proving_ground")` delegates to `evaluate_proving_ground_exit`. A continuum stamp that fails this law is healed to incomplete.

## Consequences

### Positive

- Birth certificate JSON and audit-scan cannot complete Proving Ground.
- Operator HUD can paint the same AND the engine uses.
- REAL stays a human gate after a machine exam, not instead of one.

### Negative

- Honest Proving Ground needs a living shadow clock plus eval-only purged folds. That is the point.
- A one-shot evaluator cannot pass. The clock stays open until evidence exists.

## Alternatives considered

1. Keep promotion **or** shadow — rejected; one milestone is not a driving test.
2. Grade cert walls on Birth certificate JSON — rejected; wrong tape, wrong phase.
3. Scan `promotion_gate_audit.jsonl` for `passed=true` — rejected; foreign rows are not this run.
4. Soft-complete lab stamp — rejected in production (same as ADR-0049 / ADR-0050 / ADR-0051).
5. Pull human `approve-real` into Proving Ground — rejected; capital consent is REAL.
6. Reuse apprenticeship tape as n_G — rejected; walking is not the exam.

## Links

- Code: `lumina_core/maturity/proving_ground/`
- Tests: `tests/maturity/test_proving_ground_law.py`
- Gate: `lumina_core/evolution/promotion_gate.py`
- Cert kernel: `post_birth_skill_gates.certificate_oos_walls`
