# P2 slippage session calibration (2026-10-29)

Steve 14:17: fix researchers B5 before the ES/NQ cycle. CostModel **1.2.0**.
This file documents the slippage table. It is not a template pre-register and
does not retune DSR/PBO, catalog geometry, or holdout seal `85e4588f`.

## What was wrong

CostModel 1.1.0 already used bar true-range as the vol term (no fixed
`volatility_price=2.0`). Inverse volume still compared each bar to a mixed
21-bar ADV. An ETH 1-minute bar with ~1/20 of RTH volume against a window that
includes the cash open got `slip_scale ≈ 20`, so overnight looked several times
more expensive than RTH for the same true range. Researchers: that punishes ETH
while some templates can trade Globex.

## Locked table (not fit on the P2 tape or holdout)

| field | RTH | ETH | reason |
|---|---|---|---|
| vol term | bar true range / 0.25 | same | B5; never a fixed 2.0 |
| ADV | last 21 **RTH** bars | last 21 **ETH** bars | same-session denominator |
| slippage coefficient | 0.10 | 0.10 | ADR-0055 starting point; explicit per-session knobs |
| volume scale cap | 4 | 4 | dead bar cannot explode to 1e6 ticks |
| impact | 0.10 * vol_ticks * sqrt(qty / session ADV) | same | unchanged shape, session ADV |
| SIM fills | none in-repo | none | coefficients not retuned if files appear later |

Formula:

`slippage_ticks = session_coefficient * (true_range / tick_size) * min(session_ADV / volume, 4)`

## What this is not

- Not a fitted ETH discount to make the 12 templates look better.
- Not a holdout calibration.
- Not a change to ADR-0055 commission (MES/MNQ $0.94/side, ES/NQ $2.87/side).
- Catalog templates stay RTH-filtered; the ETH coefficient still matters for
  Globex-filter variants and for honest per-bar costs on mixed tapes.

## Fail-closed

If a later SIM-fill archive exists, keep these coefficients until a new Steve
OK. Do not fit them on MES/MNQ/ES/NQ OOS or on holdout.
