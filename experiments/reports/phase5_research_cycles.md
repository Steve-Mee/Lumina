# Phase 5 P2 research cycles

- generated_at: `2026-10-28T19:16:56.505649+00:00`
- hypotheses: `24` tested: `0` killed: `0` survivors: `0`
- kill_rate: `n/a` (expectation > 0.90, diagnostic flag `not_tested`)
- stopped: `True` reason: `no_usable_real_market_data`
- real data usable: `False`

## Data requirement (if unusable)

- **instruments**: at least one of ES, NQ, MES, MNQ
- **bar_size**: 1-minute RTH last bars preferred (ADR-0053); 5m or 1d accepted
- **period**: >= 241 bars (walk-forward 60 IS + 6*30 OOS); prefer >= 252 trading days
- **format**: CSV/JSONL columns timestamp,open,high,low,close,volume (UTC) or playground .bars
- **paths**: $LUMINA_RESEARCH_DATA_DIR/{ROOT}/{1m|5m|1d}/*.csv ; data/research/{ROOT}/{1m|5m|1d}/*.csv ; reports/playground_bar_archive/{ROOT}.bars
- **code**: lumina_research.cycles.data.discover_data

- searched: /workspace/data/research, /workspace/reports/playground_bar_archive
- missing instruments: ES, NQ, MES, MNQ

## Modeled costs vs briefed bands (CostModel unchanged)

| root | modeled one-way ticks | band | in_band | note |
|---|---|---|---|---|
| ES | 1.538 | 0.5-1.5 | False | modeled ticks sit outside the briefed average band; CostModel is unchanged — calibrate on SIM fills, do not retune the gate |
| NQ | 1.882 | 0.5-1.5 | False | modeled ticks sit outside the briefed average band; CostModel is unchanged — calibrate on SIM fills, do not retune the gate |
| MES | 2.060 | 1.0-2.5 | True | modeled ticks sit in the briefed average band |
| MNQ | 3.188 | 1.0-2.5 | False | modeled ticks sit outside the briefed average band; CostModel is unchanged — calibrate on SIM fills, do not retune the gate |

## Costs and tick floors

| root | target ticks | stop ticks | tick $ | RT cost ticks | net target $ | net stop $ | BE win rate |
|---|---|---|---|---|---|---|---|
| ES | 8 | 4 | 12.50 | 3.075 | 61.56 | 88.44 | 0.590 |
| NQ | 12 | 4 | 5.00 | 3.764 | 41.18 | 38.82 | 0.485 |
| MES | 16 | 8 | 1.25 | 4.120 | 14.85 | 15.15 | 0.505 |
| MNQ | 16 | 8 | 0.50 | 6.376 | 4.81 | 7.19 | 0.599 |

## Hypotheses

| id | template | inst | tested | passed | death | PBO | DSR | WFE |
|---|---|---|---|---|---|---|---|---|
| hyp-mr-mes-10-1.5 | mean_reversion | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-mr-es-20-1.5 | mean_reversion | ES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-vi-mnq-10-0.55 | volume_imbalance | MNQ | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-vi-nq-20-0.65 | volume_imbalance | NQ | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-rm-mes-10-0.40 | regime_momentum | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-rm-es-10-0.40 | regime_momentum | ES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-or-mes-5-bo | opening_range_breakout | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-or-es-5-bo | opening_range_breakout | ES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-or-mnq-15-fade | opening_range_fade | MNQ | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-or-nq-15-fade | opening_range_fade | NQ | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-gap-mes-8 | overnight_gap | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-gap-es-4 | overnight_gap | ES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-vwap-mes-20-1.5 | vwap_distance | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-vwap-nq-40-2.0 | vwap_distance | NQ | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-rc-mes-20-0.25 | range_compression | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-rc-es-20-0.25 | range_compression | ES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-cr-mes-3 | close_reversal | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-cr-nq-5 | close_reversal | NQ | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-tod-mes-15 | time_of_day_inventory | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-tod-es-15 | time_of_day_inventory | ES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-pb-mnq-20 | trend_pullback | MNQ | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-pb-nq-20 | trend_pullback | NQ | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-vx-mes-20 | volatility_expansion | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-vx-es-20 | volatility_expansion | ES | False | False | not_tested_no_real_data | n/a | n/a | n/a |

## Survivors

None. Expected: most economically simple hypotheses die at the Validation Gate.
