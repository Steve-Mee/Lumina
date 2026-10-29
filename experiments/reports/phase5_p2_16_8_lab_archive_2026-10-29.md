# 16/8 1m brackets — lab archive (not economic falsification)

Date: 2026-10-29. Advisory: stop 16/8 as a research programme; archive it as a
lab result. The 12 first-cycle families and their ES/NQ 16/8 translations are
**not** refuted economic hypotheses. What was measured is: **fixed 16-tick
target / 8-tick stop, stop-on-touch, target trade-through, 16-bar time-stop,
on 1m OHLC**, after CostModel 1.2.0.

## What the lab showed

| cycle | files | result |
|---|---|---|
| MES/MNQ 1.1.0 | `phase5_p2_results.md` (frozen) | 12/12 kill |
| MES/MNQ 1.2.0 | `phase5_p2_costfix_mes_mnq_results.md` | 12/12 kill; gross already negative; hitrate < BE 0.333 |
| ES 16/8 translations | `phase5_p2_es_nq.md` | 9/9 kill, same pattern |
| NQ 16/8 | not run | D13 null leaked drift; templates closed. Null now reliable (audit 2026-10-29); still not a 16/8 rerun |

Kills were on **gross** (hitrate ~0.29, 0/8 +OOS). Not a cost artefact.

## What this does not mean

It does not mean mean-reversion, opening-range, gap, VWAP, or momentum is
false. It means that geometry on that horizon clipped or over-traded the
stated idea. The catalog 16/8 rows stay in git as the locked first-cycle
objects. They are not deleted and not re-run. Next cycle uses ATR/points
session-horizon geometry (`phase5_p2_atr_geometry_preregister_2026-10-29.md`).
