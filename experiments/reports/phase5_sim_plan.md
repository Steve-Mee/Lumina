# Phase 5 P3 SIM plan (do not start in this PR)

This is a plan. No SIM session, paper order, or live order is opened here.

## Entry conditions (all required)

- At least 3 independent, low-correlation Validation Gate survivors.
- Correlation is measured on OOS net returns; a cluster of MES+ES clones does not count as independent.
- Survivors still carry a valid sealed gate passage. Risk Core is untouched.

## Duration

- Run until **both** clocks are satisfied: >= 60 trading days **or**
  >= 100 trades, **whichever is later**.
- Live is not discussed until that clock completes and the band below holds.

## Acceptable band

- Realized Sharpe not structurally below 70% of median expected OOS.
- Drawdown not greater than 1.5x expected (same 1.5x material-break definition).
- Structural underperformance over multiple windows → de-weight and return the name to research.
- Capital-preservation violations must remain 0.

## Fills and costs

- Use the existing four-leg CostModel. Calibrate slippage/impact on SIM fills; do not retune gate floors.
- Limit orders use trade-through plus a volume condition (or a probabilistic fill rate). No zero-slippage.
- ES/NQ briefed average 0.5-1.5 ticks plus impact; MES/MNQ 1-2.5 ticks, modelled separately.

## Forbidden in this PR

- Starting a SIM session.
- Placing, sizing, or cancelling orders.
- Writing live Risk Core, PromotionGate, or Fabric state.

