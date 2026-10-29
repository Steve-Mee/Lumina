# Phase 5 P2 research cycles

- generated_at: `2026-10-29T14:47:53.904245+00:00`
- hypotheses: `12` tested: `9` killed: `9` survivors: `0`
- kill_rate: `1.0000` (expectation > 0.90, diagnostic flag `expected_high_kill`)
- stopped: `False` reason: ``
- real data usable: `True`

## Data requirement (if unusable)

- **instruments**: P2 first cycle: MES and MNQ 1m; ES/NQ accepted later
- **bar_size**: NT8 1-minute bars first; 5m or 1d accepted only as a documented fallback
- **period**: recent 2-3 years; train split must still have >= 241 bars after the holdout lock
- **holdout**: last 9 calendar months (allowed 6-12); P2 NT8 tapes pin 2026-01-28T23:00:00Z (legacy 2026-01-29T00:00:00Z recorded, holdout unopened); access_bars(purpose=selection|tuning|calibration|gate) fails closed on holdout timestamps
- **format**: UTF-8 CSV header timestamp,open,high,low,close,volume (UTC ISO-8601 with offset)
- **paths**: $LUMINA_RESEARCH_DATA_DIR/{MES,MNQ}/1m/nt8_{mes,mnq}_1m.csv ; data/research/{MES,MNQ}/1m/*.csv ; optional data/research/VIX/1d/vix.csv for regime labels
- **code**: lumina_research.cycles.data.discover_data + lumina_research.cycles.holdout.access_bars

- searched: $LUMINA_RESEARCH_DATA_DIR, /workspace/data/research, /workspace/reports/playground_bar_archive
- missing instruments: (none)

## Modeled costs vs instrument-specific USD/contract bands

| root | comm $/side | comm $ RT | half-spread $ | RTH $/contract | RTH bp | ETH $/contract | band $/contract | in_band | note |
|---|---|---|---|---|---|---|---|---|---|
| ES | 2.87 | 5.74 | 6.250 | 14.170 | 0.567 | 14.170 | 3.00-12.00 | False | modeled RTH one-way USD/contract sits outside the instrument-specific dollar band; CostModel coefficient is not retuned on holdout (see slippage_calibration) |
| NQ | 2.87 | 5.74 | 2.500 | 7.390 | 0.924 | 7.390 | 3.00-12.00 | True | modeled RTH one-way USD/contract sits in the instrument-specific dollar band |
| MES | 0.94 | 1.88 | 0.625 | 2.070 | 0.828 | 2.070 | 1.50-6.00 | True | modeled RTH one-way USD/contract sits in the instrument-specific dollar band |
| MNQ | 0.94 | 1.88 | 0.250 | 1.392 | 1.740 | 1.392 | 1.20-5.00 | True | modeled RTH one-way USD/contract sits in the instrument-specific dollar band |

## Costs and tick floors

| root | target ticks | stop ticks | tick $ | RT cost ticks | net target $ | net stop $ | BE win rate |
|---|---|---|---|---|---|---|---|
| ES | 16 | 8 | 12.50 | 2.267 | 171.66 | 128.34 | 0.428 |
| NQ | 16 | 8 | 5.00 | 2.956 | 65.22 | 54.78 | 0.456 |

## Hypotheses

| id | template | inst | tested | passed | death | PBO | DSR | WFE |
|---|---|---|---|---|---|---|---|---|
| hyp-p2c-mr-es-10-1.5 | mean_reversion | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a |
| hyp-p2c-rm-es-10-0.40 | regime_momentum | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a |
| hyp-p2c-or-es-5-bo | opening_range_breakout | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a |
| hyp-p2c-gap-es-8 | overnight_gap | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a |
| hyp-p2c-vwap-es-20-1.5 | vwap_distance | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a |
| hyp-p2c-rc-es-20-0.25 | range_compression | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a |
| hyp-p2c-cr-es-3 | close_reversal | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a |
| hyp-p2c-tod-es-15 | time_of_day_inventory | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a |
| hyp-p2c-vx-es-20 | volatility_expansion | ES | True | False | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a |
| skipped-p2c-vi-nq-10-0.55 | volume_imbalance | NQ | False | False | not_tested_control_failed | n/a | n/a | n/a |
| skipped-p2c-or-nq-15-fade | opening_range_fade | NQ | False | False | not_tested_control_failed | n/a | n/a | n/a |
| skipped-p2c-pb-nq-20 | trend_pullback | NQ | False | False | not_tested_control_failed | n/a | n/a | n/a |

## Survivors

None. Expected: most economically simple hypotheses die at the Validation Gate.

## Holdout seal

- sha256: `454b8d1f7fd8b0fe0ee43b9c4431515be3912e4859a6a268372ec1c3aff5abd4`
- previous_seal: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: n_days=599 walk-forward is_size=46 oos_size=69 target_windows=8 units=globex_session_days
- n_days: `599`
- pin: `2026-01-28T23:00:00+00:00` Globex session boundary (legacy `2026-01-29T00:00:00Z` recorded)
- holdout sealed and unopened for ranking, tuning, and gate calibration
- 1m four-leg costs (ADR-0055/1.2 RTH-ETH session slippage) then Globex session-day resample
- floors unchanged: DSR>=0.95, PBO hard 0.50 / warn 0.25, min 6 OOS; static rules use A2 not WFE
- geometry is pre-registered per template; shadow only; zero orders; S0 freeze untouched
- positive_control_detected: `True` null_detected: `False`
- control: Planted edge: at the first RTH bar of each session, the control knows the sign of that session's last-RTH-close minus first-RTH-open (unadjusted). It holds that direction until RTH close (session flatten, C10). Brackets are 1:1 20000/20000 ticks (CME 20% limit-move ceiling; not an 8-tick clip) so a shuffled 50% null is not a 2R artefact. time_stop_bars=2000 cannot fire inside one RTH session. Four-leg costs unchanged. Known size is the session RTH open-to-close move minus costs. | ES: planted detected, null rejected; NQ: FAILED positive control was not detected or the null control looked like an edge


## Holdout evaluation (survivors only, one pass)

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

