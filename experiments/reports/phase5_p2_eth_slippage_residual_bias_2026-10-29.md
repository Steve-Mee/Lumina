# Residual ETH-slippage bias (CostModel 1.2.0) — 2026-10-29

Advisory item 6: accept CostModel **1.2.0** as the basis; document residual
ETH-slippage bias; do **not** run SIM-fill calibration in this cycle (action 6:
no SIM orders).

## What 1.2.0 already fixed

- Vol term = bar true-range / tick (no fixed `volatility_price=2.0`).
- ADV = last 21 bars of the **same** session type (`causal_session_adv`).
- Inverse-volume scale capped at 4.
- Explicit per-session knobs: RTH coefficient **0.10**, ETH coefficient **0.10**.

Source: ADR-0064, `phase5_p2_slippage_rth_eth_2026-10-29.md`. Coefficients are
the ADR-0055 starting point. They are **not** fit on this tape or the sealed
holdout.

## Residual bias that remains

1. **ETH coefficient = RTH coefficient.** Overnight *spreads* and queue
   position are not measured. Half-spread stays **0.5 ticks** on every
   session. If ETH effective spread is wider than 0.5 ticks, overnight costs
   are understated.
2. **No SIM fill archive in-repo.** `load_slippage_calibration` finds zero
   fill files and leaves both knobs at 0.10. Action 6 forbids SIM orders, so
   this cycle does not collect fills.
3. **True-range vol term on thin ETH bars.** A quiet overnight bar with a
   large range still pays `0.10 * range/tick * min(ADV/volume, 4)`. That can
   overstate or understate vs a real fill, depending on whether the range is
   noise or a gap-through.
4. **RTH-only templates** (this ATR grid, session_filter=`rth`) mostly dodge
   ETH slippage. Residual ETH bias still matters for Globex-filter variants,
   gap opens that inherit overnight range, and any later SIM calibration.

## What would change the knobs

A new Steve OK plus a SIM (or live) fill archive. Do not fit coefficients on
MES/MNQ/ES/NQ OOS or on holdout. Until then CostModel 1.2.0 + this note is
the honest statement of residual bias.
