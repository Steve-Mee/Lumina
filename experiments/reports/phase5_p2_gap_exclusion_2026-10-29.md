# P2 gap exclusion (action 3) — 2026-10-29

Binding: onderzoeksteam advisory
`docs/research/ONDERZOEKERS-ANALYSE-4MARKTEN-20261029T1603.md` (content sha256
`83476aa358b515f018002c79cf83caa33e335d281cc107e0f61b4be94b474df7`, freeze
commit `51872204`). Pre-register
`phase5_p2_atr_geometry_preregister_2026-10-29.md`. Holdout pin
`2026-01-28T23:00:00Z` stays **closed**. No MES fill. No re-export.

Counts are from the mounted PIT CSVs under `$LUMINA_RESEARCH_DATA_DIR`
(`/tmp/lumina_p2_data` in this run). Typical weekday Globex minute count is
1380. Date = UTC calendar day of the bar timestamp.

## TRAIN — 2025-07-13 / 14 / 15

| day | ES | NQ | MES | MNQ | decision |
|---|---|---|---|---|---|
| 2025-07-13 | **0** | 119 (Sunday Globex) | 119 | **0** | exclude **ES** and **MNQ** only |
| 2025-07-14 | **0** | 1380 | 1379 | **0** | exclude **ES** and **MNQ** only |
| 2025-07-15 | **671** (half) | 1380 | 1380 | **668** (half) | exclude **ES** and **MNQ** only |

**Instrument-specific, not all four.** NQ and MES have a full weekday session
on 14/15 and a normal Sunday Globex print on 13. Dropping them would delete
real RTH. Code: `KNOWN_GAPS` ES window `2025-07-13`..`2025-07-16` exclusive
end; MNQ window extended to include 13 (was 14–15). NQ/MES unchanged. Never
copy MES bars onto ES.

## TRAIN — 2025-11-28 (already `*` / all four)

| day | ES | NQ | MES | MNQ |
|---|---|---|---|---|
| 2025-11-28 | 444 | 450 | 451 | 451 |

Thin on every root (CME outage). Already excluded as `GapWindow("*", ...)`.
Not ES-only.

## HOLDOUT — recorded, unused

Pin closed. These windows are in `KNOWN_GAPS` so a later holdout eval cannot
score incomplete ES days. They are **not evaluated now**. Max 1–2 holdout
evals total; this cycle uses **zero**.

| day | ES | NQ | MES | MNQ |
|---|---|---|---|---|
| 2026-04-22 | **0** | 1380 | 1380 | 1380 |
| 2026-04-23 | **0** | 1380 | 1380 | 1380 |
| 2026-04-24 | **0** | 1261 | 1261 | 1261 |
| 2026-04-26 | **0** | 119 | 119 | 119 |
| 2026-04-27 | **119** | 1380 | 1380 | 1380 |
| 2026-05-08 | **0** | 1261 | 1261 | 1261 |
| 2026-05-11 | **0** | 1380 | 1380 | 1380 |
| 2026-05-12 | **119** | 1380 | 1380 | 1380 |

ES-only holes. NQ/MES/MNQ present. No MES fill. Windows stored as ES-only.

## What this is not

- Not an NT8 re-export / re-seal.
- Not a holdout opening.
- Not interpolation or MES→ES stitching.
