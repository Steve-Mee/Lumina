# P2 instrument cost bands (2026-10-29)

Steve 14:17 / researchers B4. Locked before the cost-fix rerun and the ES/NQ
cycle. Does not rewrite first-cycle templates, DSR/PBO floors, or seal
`85e4588f`.

## ADR-0055 Free commission (per contract)

| root | tick $ | comm $/side | comm $ RT | half-spread $ (0.5 tick) |
|---|---|---|---|---|
| ES | 12.50 | 2.87 | 5.74 | 6.250 |
| NQ | 5.00 | 2.87 | 5.74 | 2.500 |
| MES | 1.25 | 0.94 | 1.88 | 0.625 |
| MNQ | 0.50 | 0.94 | 1.88 | 0.250 |

Micros share the same dollar ticket. MNQ is expensive **in ticks** (1.88 ticks
of commission) which is why a 0.5–1.5 tick band was never a MNQ band.

## Four-leg one-way band ($/contract)

| root | band $/contract | reference notional | bp at band mid (informational) |
|---|---|---|---|
| ES | 3.00–12.00 | 250_000 | — |
| NQ | 3.00–12.00 | 80_000 | — |
| MES | 1.50–6.00 | 25_000 | — |
| MNQ | 1.20–5.00 | 8_000 | — |

Modeled one-way = commission + half-spread + session slippage + sqrt impact
on the RTH reference snapshot (volume=ADV=10_000, true range=$1). ETH uses
the same snapshot with `session=eth`. Coefficients are not fit on holdout.

## Same-bar round trip

A 16/8 stop that fills and exits on one 1m bar must still pay **two**
commission sides. Reporting 0 position on that bar was the MNQ cost/trade
artefact (D14 commission/trade ≪ $1.88 while BE was higher than MES).
