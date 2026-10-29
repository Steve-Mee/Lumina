# P2 four-instrument cycle — pre-registration (2026-10-29)

Locked **before** any cost-fix rerun or ES/NQ run. Steve OK 2026-10-29 14:13
(ES/NQ) and 14:17 (fix costs first). Cost commits already on this branch:
`86fc18c0` (RTH/ETH slippage 1.2.0), `436b00a9` ($/contract bands + same-bar
commission). This file does **not** rewrite
`phase5_first_cycle_preregister.md`, the 24 catalog variants, ADR-0062/0063,
`phase5_p2_results.md`, `phase5_research_cycles.json`, or holdout seal
`85e4588fde77159315a72bdaa722d6487f93bbad9bf24999311f893950489d40`.

## Why

Researchers F18: also ES/NQ (lower cost vs tick value) after implementation
fixes. Steve: same 12 families, same per-template geometry as the locked
MES/MNQ first cycle, not the catalog 8/4 / different-lookback duplicates.

## Floors (unchanged)

- DSR >= 0.95
- PBO hard 0.50 / warn 0.25
- Static A2: median OOS > 0, >= 60% +OOS, no structural decay
- Holdout pin `2026-01-28T23:00:00Z` closed (no selection/tuning/calibration)
- Propose-only; no SIM/REAL orders; Risk Core untouched

## Costs (already committed; used here, not retuned)

- CostModel 1.2.0: true-range vol term, RTH/ETH session-local ADV, cap 4
- ADR-0055 Free: MES/MNQ $0.94/side ($1.88 RT), ES/NQ $2.87/side ($5.74 RT)
- Bands $/contract: ES/NQ 3–12, MES 1.50–6.00, MNQ 1.20–5.00, plus bp
- Same-bar round trips pay both commission sides

## MES/MNQ cost-fix rerun (12 configs, new files)

Same locked first-cycle ids and 16/8 (or family) geometry. Write
`phase5_p2_costfix_mes_mnq_results.md` (+ json). **Do not overwrite**
`phase5_p2_results.md` / `phase5_research_cycles.json` (CostModel 1.1.0
baseline). Report the delta: trades, hitrate vs BE, gross, net, +OOS, median
OOS, death, D14 four-leg, cost/trade vs gross/trade.

| config_id | template | instrument | lookback | threshold | mode | target/stop |
|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | mean_reversion | MES | 10 | 1.5 | fade | 16/8 |
| vi-mnq-10-0.55 | volume_imbalance | MNQ | 10 | 0.55 | fade | 16/8 |
| rm-mes-10-0.40 | regime_momentum | MES | 10 | 0.40 | follow | 16/8 |
| or-mes-5-bo | opening_range_breakout | MES | 5 | 0.0 | breakout | 16/8 |
| or-mnq-15-fade | opening_range_fade | MNQ | 15 | 0.0 | fade | 16/8 |
| gap-mes-8 | overnight_gap | MES | 1 | 8.0 | fade | 16/8 |
| vwap-mes-20-1.5 | vwap_distance | MES | 20 | 1.5 | fade | 16/8 |
| rc-mes-20-0.25 | range_compression | MES | 20 | 0.25 | breakout | 16/8 |
| cr-mes-3 | close_reversal | MES | 3 | 0.0 | fade | 16/8 |
| tod-mes-15 | time_of_day_inventory | MES | 15 | 0.0 | fade | 16/8 |
| pb-mnq-20 | trend_pullback | MNQ | 20 | 0.0 | follow | 16/8 |
| vx-mes-20 | volatility_expansion | MES | 20 | 0.75 | breakout | 16/8 |

## ES/NQ translation (12 configs, new files)

MES→ES, MNQ→NQ. Same lookback, threshold, mode, 16/8 ticks. **Not** catalog
rows `mr-es-20-1.5`, `vi-nq-20-0.65`, `gap-es-4`, `vwap-nq-40-2.0`, `cr-nq-5`,
or any 8/4 duplicate. Prefix `p2c-` so ids do not collide with the 24-variant
catalog. Write `phase5_p2_es_nq_results.md` (+ json).

| source | config_id | instrument | lookback | threshold | mode | target/stop |
|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | p2c-mr-es-10-1.5 | ES | 10 | 1.5 | fade | 16/8 |
| vi-mnq-10-0.55 | p2c-vi-nq-10-0.55 | NQ | 10 | 0.55 | fade | 16/8 |
| rm-mes-10-0.40 | p2c-rm-es-10-0.40 | ES | 10 | 0.40 | follow | 16/8 |
| or-mes-5-bo | p2c-or-es-5-bo | ES | 5 | 0.0 | breakout | 16/8 |
| or-mnq-15-fade | p2c-or-nq-15-fade | NQ | 15 | 0.0 | fade | 16/8 |
| gap-mes-8 | p2c-gap-es-8 | ES | 1 | 8.0 | fade | 16/8 |
| vwap-mes-20-1.5 | p2c-vwap-es-20-1.5 | ES | 20 | 1.5 | fade | 16/8 |
| rc-mes-20-0.25 | p2c-rc-es-20-0.25 | ES | 20 | 0.25 | breakout | 16/8 |
| cr-mes-3 | p2c-cr-es-3 | ES | 3 | 0.0 | fade | 16/8 |
| tod-mes-15 | p2c-tod-es-15 | ES | 15 | 0.0 | fade | 16/8 |
| pb-mnq-20 | p2c-pb-nq-20 | NQ | 20 | 0.0 | follow | 16/8 |
| vx-mes-20 | p2c-vx-es-20 | ES | 20 | 0.75 | breakout | 16/8 |

## D13 control (per instrument)

Same session-hold respec as ADR-0063, run separately on each tape that is
present and PIT-correct:

| field | value |
|---|---|
| session_filter | `rth` |
| session_end_flatten | true |
| target/stop | 20000 / 20000 (1:1) |
| time_stop_bars | 2000 |
| null seed | 20261029 |
| planted edge | session last-RTH-close − first-RTH-open (unadjusted) |

If planted is not detected or null looks like an edge: **stop that instrument**,
diagnose, do not iterate geometry without a new Steve OK. Other instruments
with a passing control may still run.

## Data and seal

- Only real PIT NT8 1m continuous unadjusted CSVs, same pipeline as MES/MNQ
  (`$LUMINA_RESEARCH_DATA_DIR/{ES,NQ,MES,MNQ}/1m/*.csv`).
- MES/MNQ seal `85e4588f` is **reused**, not rewritten.
- ES/NQ get `phase5_p2_es_nq_holdout_seal.json` at the same pin if both tapes
  exist and hashes are recorded. Missing or non-PIT ES/NQ: fail-closed for
  those roots and report the exact files/hashes needed. Do not invent bars.
- Raw CSVs are never committed.

## Holdout eval

Only if a survivor already passed the charter gate. Report, do not promote.

## Comparison (required in the run report)

Per config and a four-root summary: trades, hitrate vs BE, gross, net, +OOS,
median OOS, death, D14 four-leg, **cost/trade vs gross/trade** for MES, MNQ,
ES, NQ (ES/NQ cells empty if that tape was fail-closed).
