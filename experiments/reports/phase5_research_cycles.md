# Phase 5 P2 research cycles

- generated_at: `2026-10-29T08:35:14.905205+00:00`
- hypotheses: `12` tested: `12` killed: `12` survivors: `0`
- kill_rate: `1.0000` (expectation > 0.90, diagnostic flag `expected_high_kill`)
- stopped: `False` reason: ``
- real data usable: `True`

## Data requirement (if unusable)

- **instruments**: P2 first cycle: MES and MNQ 1m; ES/NQ accepted later
- **bar_size**: NT8 1-minute bars first; 5m or 1d accepted only as a documented fallback
- **period**: recent 2-3 years; train split must still have >= 241 bars after the holdout lock
- **holdout**: last 9 calendar months (allowed 6-12); P2 NT8 tapes pin 2026-01-29T00:00:00Z; access_bars(purpose=selection|tuning|calibration|gate) fails closed on holdout timestamps
- **format**: UTF-8 CSV header timestamp,open,high,low,close,volume (UTC ISO-8601 with offset)
- **paths**: $LUMINA_RESEARCH_DATA_DIR/{MES,MNQ}/1m/nt8_{mes,mnq}_1m.csv ; data/research/{MES,MNQ}/1m/*.csv ; optional data/research/VIX/1d/vix.csv for regime labels
- **code**: lumina_research.cycles.data.discover_data + lumina_research.cycles.holdout.access_bars

- searched: $LUMINA_RESEARCH_DATA_DIR, data/research, reports/playground_bar_archive
- missing instruments: ES, NQ

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
| hyp-mr-mes-10-1.5 | mean_reversion | MES | True | False | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |
| hyp-vi-mnq-10-0.55 | volume_imbalance | MNQ | True | False | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |
| hyp-rm-mes-10-0.40 | regime_momentum | MES | True | False | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |
| hyp-or-mes-5-bo | opening_range_breakout | MES | True | False | missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |
| hyp-or-mnq-15-fade | opening_range_fade | MNQ | True | False | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |
| hyp-gap-mes-8 | overnight_gap | MES | True | False | missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |
| hyp-vwap-mes-20-1.5 | vwap_distance | MES | True | False | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |
| hyp-rc-mes-20-0.25 | range_compression | MES | True | False | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |
| hyp-cr-mes-3 | close_reversal | MES | True | False | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |
| hyp-tod-mes-15 | time_of_day_inventory | MES | True | False | missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |
| hyp-pb-mnq-20 | trend_pullback | MNQ | True | False | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |
| hyp-vx-mes-20 | volatility_expansion | MES | True | False | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a |

## Survivors

None. Expected: most economically simple hypotheses die at the Validation Gate.

## Holdout seal

- sha256: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: walk-forward is_size=43 oos_size=69 target_windows=8
- pin: `2026-01-29T00:00:00+00:00` before template ranking, tuning, or gate calibration
- 1m four-leg costs (ADR-0055) then Globex session-day resample for WF/CPCV/DSR
- floors unchanged: DSR>=0.95, WFE>=0.5, PBO hard 0.50 / warn 0.25, min 6 OOS
- MES/MNQ tick floors 16/8; commission $0.94; slippage band 1-2.5 ticks
- shadow only; zero orders; S0 freeze untouched


## Holdout evaluation (survivors only, one pass)

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

