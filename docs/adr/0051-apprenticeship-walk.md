# ADR-0051: Apprenticeship — walk as a professional on SIM, no stamps

**Status:** Accepted  
**Date:** 2026-09-19  
**Deciders:** LUMINA Engineering (Steve + Grok)  
**Refines:** [organism-maturation-phases.md](./organism-maturation-phases.md), [ADR-0046](./0046-birth-foundation-evolvable-plant.md) relocated S6 Sharpe/DD  
**Relates:** [ADR-0049](./0049-awakening-eyes-open.md), [ADR-0050](./0050-playground-first-contact.md), [ADR-0027](./0027-lumina-maturation-ladder.md)

## Context

Playground (ADR-0050) is first contact: crawl in NT SIM, n_P≥150, WR≥geometry BE, mean R≥0. Apprenticeship is the next organ: **walk for consecutive session days under REAL rules, still on fictional capital**.

The production runner was a one-shot evaluator. It stamped `sim_real_guard_stable` from `READY_FOR_REAL`, allowed `apprenticeship_eval_ok` soft-complete, and fed `MultiDaySimRunner` (a DNA backtest) that invented per-day PnL, Sharpe as `|pnl|/100`, and dates counted backwards from today. Former Birth S6 (`Sharpe ≥ 0.20`, `DD ≤ 12%`) lived in `post_birth_skill_gates.risk_discipline` and was never AND-ed. The old stability report demanded Sharpe > 1.8 and an evolution-proposal trend — later walls, wrong phase.

A backtest is not a session day. A JSON day file is not a fill. READY_FOR_REAL from a forged ledger is not walking.

## Decision

Apprenticeship exit is fail-closed AND. Soft-complete may warn on the hub. It must not set `ok=True`.

| Invariant | Law |
|-----------|-----|
| Entry | Playground completed per ADR-0050. Birth freeze intact. Policy SHA = playground child, ≠ Birth π* |
| Habitat | NT SIM. Mode **= `sim_real_guard`**. `sim` is Playground. REAL = halt |
| Envelope | Operator-sealed SIM envelope. Missing file = unsealed. Breach = fail |
| n_A ≥ 150 | Policy-only SIM **closes on the apprenticeship tape**. Playground tape does not count. Below 150 = INCONCLUSIVE |
| Policy-only | Sharpe, DD, expectancy, process-R from policy closes. Plant FORCE_* = airframe |
| Occupancy | Exam band 25–75% plant-flat |
| Process-R | `median_loss_r` ≤ 1.5. No policy closes → missing, not 0 |
| Green session days | n_D ≥ 5 consecutive futures session days (Fri→Mon counts; weekend is not a gap). Green iff ≥1 policy close **and** session expectancy (pnl/trades) > 0 **and** no constitution event that day. Backdated JSON ≠ a day. One backtest ≠ 5 days |
| Risk discipline | Sharpe ≥ 0.20 **and** max DD ≤ 12% of $50k MES 1-lot on this tape |
| Sharpe | Daily returns `day_pnl / 50000`, then `mean/std * sqrt(252)`. <5 session days or std=0 → missing. Never `|pnl|/100` |
| DD | Peak-to-trough of cumulative MES 1-lot equity vs $50k. Clip physics = Birth S5 |
| Constitution 0 | risk_events=0, var_breach=0, envelope not breached, daily kill not hit, mode never REAL |
| Never-stop | Crash / NT down / occupancy crash <0.25 → resume the **same** tape. No wipe, no `expand_data`, no floor-cut. `recovery_ok` after freeze held through ≥1 session day |
| Soft-complete | Must not set `ok=True` |
| Clock | Open until AND, operator stop, or 3 stall retries. Incomplete ≠ failed |

`sim_real_guard_stable` / READY_FOR_REAL may fire **only as a consequence** of this AND. `generate_stability_report` is not the pass SSOT. `MultiDaySimRunner` must not write apprenticeship days.

**Not in this AND:** Sharpe 1.8, evolution-proposal trend, Twin-watch, cert OOS 48/0.35/8% (Proving Ground), WR≥BE (Playground), a single fill, Birth fitness.

SSOT: `lumina_core/maturity/apprenticeship/law.py`. Progress: `state/lumina_apprenticeship_progress.json`. Tape: `state/lumina_apprenticeship_tape.jsonl`. Day ledger: `state/lumina_apprenticeship_days.jsonl` (derived from tape only). `evaluate_exit_proofs("apprenticeship")` delegates to `evaluate_apprenticeship_exit`. A continuum stamp that fails this law is healed to incomplete.

## Consequences

### Positive

- Backtest JSON days and READY_FOR_REAL stamps cannot complete Apprenticeship.
- Operator HUD can paint the same AND the engine uses.
- Playground crawl stays the parent skill; Birth plant stays frozen.

### Negative

- Honest Apprenticeship needs five consecutive live NT SIM session days. That is the point.
- A one-shot evaluator cannot pass. The clock stays open overnight.

## Alternatives considered

1. Keep MultiDaySimRunner day files — rejected; a backtest is not a venue session.
2. Pass on `sim_real_guard_stable` milestone — rejected; stamps are not walking.
3. Use stability-report Sharpe > 1.8 + proposal trend — rejected; those walls are not this phase.
4. Soft-complete lab stamp — rejected in production (same as ADR-0049 / ADR-0050).
5. Pull cert OOS or WR≥BE into Apprenticeship — rejected; those walls have homes.

## Links

- Code: `lumina_core/maturity/apprenticeship/`
- Tests: `tests/maturity/test_apprenticeship_law.py`
- Risk kernel: `post_birth_skill_gates.risk_discipline`
