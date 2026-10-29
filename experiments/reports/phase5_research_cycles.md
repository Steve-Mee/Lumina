# Phase 5 P2 research cycles

- generated_at: `2026-10-28T20:35:18.946543+00:00`
- hypotheses: `12` tested: `0` killed: `0` survivors: `0`
- kill_rate: `n/a` (expectation > 0.90, diagnostic flag `not_tested`)
- stopped: `True` reason: `no_usable_real_market_data`
- real data usable: `False`

## Data requirement (if unusable)

- **instruments**: P2 first cycle: MES and MNQ 1m; ES/NQ accepted later
- **bar_size**: NT8 1-minute bars first; 5m or 1d accepted only as a documented fallback
- **period**: recent 2-3 years; train split must still have >= 241 bars after the holdout lock
- **holdout**: last 9 calendar months (allowed 6-12) from the last bar are locked; access_bars(purpose=selection|tuning|calibration|gate) fails closed on holdout timestamps
- **format**: UTF-8 CSV header timestamp,open,high,low,close,volume (UTC ISO-8601 with offset)
- **paths**: $LUMINA_RESEARCH_DATA_DIR/{MES,MNQ}/1m/nt8_{mes,mnq}_1m.csv ; data/research/{MES,MNQ}/1m/*.csv ; optional data/research/VIX/1d/vix.csv for regime labels
- **code**: lumina_research.cycles.data.discover_data + lumina_research.cycles.holdout.access_bars

- searched: /tmp/empty-research-data, /workspace/data/research, /workspace/reports/playground_bar_archive
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
| MES | 16 | 8 | 1.25 | 4.120 | 14.85 | 15.15 | 0.505 |
| MNQ | 16 | 8 | 0.50 | 6.376 | 4.81 | 7.19 | 0.599 |

## Hypotheses

| id | template | inst | tested | passed | death | PBO | DSR | WFE |
|---|---|---|---|---|---|---|---|---|
| hyp-mr-mes-10-1.5 | mean_reversion | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-vi-mnq-10-0.55 | volume_imbalance | MNQ | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-rm-mes-10-0.40 | regime_momentum | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-or-mes-5-bo | opening_range_breakout | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-or-mnq-15-fade | opening_range_fade | MNQ | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-gap-mes-8 | overnight_gap | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-vwap-mes-20-1.5 | vwap_distance | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-rc-mes-20-0.25 | range_compression | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-cr-mes-3 | close_reversal | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-tod-mes-15 | time_of_day_inventory | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-pb-mnq-20 | trend_pullback | MNQ | False | False | not_tested_no_real_data | n/a | n/a | n/a |
| hyp-vx-mes-20 | volatility_expansion | MES | False | False | not_tested_no_real_data | n/a | n/a | n/a |

## Survivors

None. Expected: most economically simple hypotheses die at the Validation Gate.
