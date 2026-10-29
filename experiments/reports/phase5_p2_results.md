# Phase 5 P2 results (kill / survive)

- generated_at: `2026-10-29T08:35:14.905333+00:00`
- tested: `12` killed: `12` survivors: `0`
- kill_rate: `1.0000`
- holdout_seal: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: `walk-forward is_size=43 oos_size=69 target_windows=8`

| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS |
|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | mean_reversion | MES | kill | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -0.00434988 |
| vi-mnq-10-0.55 | volume_imbalance | MNQ | kill | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -0.0015565 |
| rm-mes-10-0.40 | regime_momentum | MES | kill | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -0.00388076 |
| or-mes-5-bo | opening_range_breakout | MES | kill | missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -0.000529516 |
| or-mnq-15-fade | opening_range_fade | MNQ | kill | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -0.00031232 |
| gap-mes-8 | overnight_gap | MES | kill | missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -1.51879e-06 |
| vwap-mes-20-1.5 | vwap_distance | MES | kill | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -0.0041107 |
| rc-mes-20-0.25 | range_compression | MES | kill | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -0.00493437 |
| cr-mes-3 | close_reversal | MES | kill | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -0.00373268 |
| tod-mes-15 | time_of_day_inventory | MES | kill | missing_or_undefined_wfe,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -1.42996e-05 |
| pb-mnq-20 | trend_pullback | MNQ | kill | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -0.00173768 |
| vx-mes-20 | volatility_expansion | MES | kill | missing_or_undefined_wfe,missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,doubt | 0.000 | 0.000 | n/a | 8 | -0.00574116 |

## Independent survivors

None.

## Holdout evaluation

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

