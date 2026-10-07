# ADR-0055: One NinjaTrader execution-cost card

**Status:** Accepted  
**Date:** 2026-10-04  
**Deciders:** Operator + LUMINA Engineering

## Context

Three fee stories were in the code at once. Birth geometry charged about $2.50 plus one invented slippage tick per side, about $5.00 per MES round trip, and that tick did not scale with quantity. The gym and the risk model charged $1.29 + $0.35 + $0.10 + $0.02 per side, $3.52 per round trip, on every root. A headless simulator defaulted to $2.55 per side. None of those numbers is the NinjaTrader card. A config dollar could replace the fee. An unknown root was priced as MES.

Constitution: truth-seeking, fail-closed, capital preservation. A green day that ignores the real ticket, or a model that invents a cheaper one, is not an honest result.

## Decision

1. **SSOT** is `lumina_core/market/nt_fees.py`. The figures are the NinjaTrader commissions page as of 2026-08-14: https://ninjatrader.com/pricing/commissions/ The page says the schedule is updated quarterly. Point values are the NinjaTrader micro-versus-mini comparison of 2026-09-29.
2. **Roots on the card:** MES, MNQ, MYM, M2K, ES, NQ, YM, RTY. Per side, micros are exchange+NFA $0.36, clearing $0.19, commission $0.39 / $0.29 / $0.09 (Free / Monthly / Lifetime). All-in $0.94 / $0.84 / $0.64. E-minis are exchange+NFA $1.39, clearing $0.19, commission $1.29 / $0.99 / $0.59. All-in $2.87 / $2.57 / $2.17. All-in is the sum of those columns. NFA is not added again.
3. **Round trip** = two sides × contracts. The fee does not depend on price.
4. **Plan.** No Monthly or Lifetime license is recorded for this desk. The unstated plan is Free, the highest all-in. `risk_controller.nt_account_plan` may be `free`, `monthly`, or `lifetime`. Any other value is refused. A dollar key in config cannot undercut the card.
5. **Unknown root, missing quantity, or a root that is not the first token of the listing** is refused. There is no MES fallback.
6. **Slippage** is not a second cash fee. Venue and paper fill prices already contain the slip that was applied. Phase scores subtract the card once. The old one-tick constant is deleted.
7. **Green day** (Playground, and the same net on the Apprenticeship day ledger): sum of living-policy closes after this fee, above zero, no constitution event. A stored `pnl` is gross. When entry and exit differ, the prices win. A SIM refill is not a result.
8. **Birth geometry, breakeven, shadow R, the gym reward, and `TradeExecutionCostModel.from_config`** read this card. Birth training is the MES card even when the tape symbol is another root, because Birth point value is already MES.
9. **This ADR does not reopen a finished Birth.** Birth exit is occupancy, process-R, and the constitution gates in ADR-0046. It is not a dollar-fee gate. The old MES fee was higher than this card, so the finished pupil was not waved through on a cheap ticket. The frozen policy stays the parent. The next training run uses this card. A running process keeps the modules it already loaded.

## Consequences

- MES Free round trip, one contract: $1.88. ES Free round trip: $5.74.
- A one-tick MES winner ($1.25) is not a green day.
- Paper and gym may still move a simulated fill price with their slippage simulators. That movement is inside the price. It is not added again as cash.
- The headless tick loop is not a phase exam. Its default cash fee is this card. Its 1.55 / 0.35 learning shape is not economic truth and cannot color a phase day.
- Changing the plan, or a later quarterly card, is a data change in this module and in `nt_account_plan`. It is not a new formula per phase.

## Links

- Code: `lumina_core/market/nt_fees.py`
- Tests: `tests/market/test_nt_fees.py`
- Playground day: `lumina_core/maturity/playground/school_days.py`, ADR-0050 amendment 2026-10-04
