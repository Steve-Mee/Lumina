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
| Entry | Awakening completed per the current-law box in ADR-0049 (First Watch). Birth freeze intact. The loaded zip is the sealed baseline. That zip may be the Birth plant. A seal whose zip or ledgers no longer match their hashes is not an entry |
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

## Amendment (2026-09-25) — clock, seal, remote operator

The AND above does not move.

- A stall is three sustained windows of 30 minutes (NT/fabric explicitly down, occupancy under 0.25 only after 500 bars, or a 500-bar run of orders with no venue fill). A flat `n_P` and a short outage are not a stall. A healthy window clears the count. `HOLD` skips one window. Three windows halt incomplete.
- `deck_live` is set by the Command Deck POST or by Telegram `DECK` from the configured chat. The runner still must not set it.
- The seal stores `daily_loss_cap` (negative floor) and `max_total_open_risk`. A boolean without those numbers is unsealed. Breach is engine telemetry (`daily_pnl` / open risk), latched. Missing telemetry while bars flow, or while `n_P > 0` and the file is absent, blocks the pass.
- Breakeven for the gate is the median stop and target on policy closes, through `economics_after_cost`. No closes, or a close without that geometry, leaves BE missing.
- The crawler zip must match `awakening_live_pi_star.json` `sha256`.
- At `n_P` 150, 300, 450, … if economics still fail, Telegram asks `CONTINUE` or `STOP`. Silence for one window halts incomplete. `CONTINUE` is not a pass.
- Operator verbs on the one Telegram poller: `STATUS`, `PAUSE`, `RESUME`, `STOP`, `DECK`, `CAP`, `SEAL`, `CONTINUE`, `HOLD`. While this clock is running the poll interval is 20s. It stays 300s otherwise.

## Amendment (2026-09-28) — open chart and portfolio floor

The AND above does not move. REAL is unchanged.

- The crawl instrument is the contract selected on an open NinjaTrader chart whose root matches the configured instrument. `MES SEP26` in config with a chart on `MES DEC26` follows the chart. No open chart for that root means no order on a guessed month. Calendar roll is only the fallback when the chart selector cannot be read.
- In SIM, the daily floor is 2% of measured Sim equity (`source=portfolio_fraction`). The dollar amount moves when equity moves by 5% or more. Unreadable equity stays unsealed. The operator does not type the floor. The SIM hard-risk cap follows that budget and never raises open risk above it. REAL caps are not written.

## Amendment (2026-10-02) — Playground is the school

The operator corrected the role. The economic AND (n_P ≥ 150, WR ≥ BE, mean R ≥ 0) moves to Apprenticeship. It is not deleted.

Playground exit is five consecutive green session days of the **living** SIM policy. A day is green only from venue policy closes on this tape: at least one close, expectancy above 0, no constitution event. Friday to Monday counts. A weekend is not a gap. A SIM cash refill is not a day and does not delete the tape.

Learning runs in the shadow book. A shadow row has no order id and cannot enter the tape. Promotion into the living policy requires 150 resolved shadow trades, mean R above 0, above the living book, and above first-touch, on a pre-registered method. Promotion resets the green-day streak. It is not a pass. Proving Ground and REAL refuse promotion.

Flat remains a legal lesson. The decoder is not flipped to manufacture a fill.

## Amendment (2026-10-04) — a green day is net of the NinjaTrader card

The five-day count does not move. A day is green only when the net sum of the closed trades that are allowed to color it is above zero and the session has no constitution event. Net is the fill result minus the round-trip fee in ADR-0055. A win that does not clear that fee is not green. A SIM cash refill is still not a day. Slippage is not subtracted a second time: it is already in the fill.

## Amendment (2026-10-04) — ADR-0056 replaces the living-policy hand and the 150-trade exam

ADR-0056 is the text that is built. On the points below, this ADR yields.

- The five green days are the venue fills of the one promoted name, not of the Birth or Awakening policy. The clock starts when that name is allowed to send orders. Before that, Playground sends no SIM order. The frozen policy does not trade.
- Promotion is that name's own forward bar, at least 30 resolved forward attempts across as many sessions as it takes, under ADR-0056. The requirement of 150 resolved shadows inside one Chicago date is buried. So is the wipe of the only evidence list.
- H1, H2, and Null B are not the search. The net-of-fee rule in the amendment above stays. Its subject is the promoted name's fills.

## Links

- Code: `lumina_core/maturity/playground/`
- Tests: `tests/maturity/test_playground_law.py`
- Economic kernel: `post_birth_skill_gates.economic_viability`
