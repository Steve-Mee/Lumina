# P2 ES/NQ tape gaps (2026-10-29)

Steve: known holes, **do not fill** from MES/MNQ without a new OK. Holdout pin
`2026-01-28T23:00:00Z` stays closed. Hashes of the continuous unadjusted CSVs:

- ES `6b23a4dded099bf251097d7f2128ef681d9233b957f62c253a81d634bb5aa759` (1_077_405 rows)
- NQ `9d41f2202cb2a638653f2502752f21daa17beb5d1b4848a227c79a8036024dc4` (1_089_745 rows)

Typical weekday Globex minute count on these tapes is 1380. Counts below are
from the mounted PIT files. MES is listed only as a witness; **no bars were copied**.

## TRAIN (before the pin — used by the Validation Gate)

| day | ES bars | NQ bars | MES bars (witness only) | note |
|---|---|---|---|---|
| 2025-07-13 | 0 | present (Sunday Globex) | present | ES hole starts Sunday evening |
| 2025-07-14 | 0 | 1380 | 1379 | ES full session missing |
| 2025-07-15 | 671 | 1380 | 1380 | ES half session |
| 2025-11-28 | 444 | 450 | 451 | both thin (CME outage); not ES-only |

Impact: one ES Globex hole of about 1.5 sessions in July 2025 sits inside the
walk-forward train. D13/C10 RTH templates skip ETH, so the Sunday-evening gap
is mostly irrelevant for RTH filters; Monday 2025-07-14 RTH is a real missing
session on ES. 2025-11-28 is thin on **all** four roots, so it does not bias
ES vs MES. Not filled.

## HOLDOUT (on or after 2026-01-28T23:00:00Z — sealed, unused for ranking)

| day | ES bars | NQ bars | note |
|---|---|---|---|
| 2026-04-22 | 0 | 1380 | |
| 2026-04-23 | 0 | 1380 | |
| 2026-04-24 | 0 | 1261 | |
| 2026-04-25 | 0 | 0 | weekend |
| 2026-04-26 | 0 | 119 | Sunday Globex |
| 2026-04-27 | 119 | 1380 | ES resume partial |
| 2026-05-08 | 0 | 1261 | |
| 2026-05-10 | 0 | present | Sunday Globex |
| 2026-05-11 | 0 | 1380 | |
| 2026-05-12 | 119 | 1380 | ES resume partial |

These cannot change kill/survive: holdout is closed for selection, tuning, and
gate calibration. They would only matter on a later holdout-eval of a survivor.

## NQ

No extra missing sessions versus ES. 2025-11-28 is the shared thin day.
