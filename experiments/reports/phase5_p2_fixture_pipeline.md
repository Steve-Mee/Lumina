# Fixture-tape 12-template pipeline (NOT the sealed NT8 holdout)

Real MES/MNQ CSVs were not mounted (`LUMINA_RESEARCH_DATA_DIR` unset). This table is the same 12 first-cycle templates on a synthetic train tape so diagnostics of the fixed pipeline are visible. Holdout eval is empty.

# Phase 5 P2 results (kill / survive)

- generated_at: `2026-10-29T10:58:02.751062+00:00`
- tested: `12` killed: `12` survivors: `0`
- kill_rate: `1.0000`
- holdout_seal: `n/a`
- previous_holdout_seal: `n/a`
- windows: `n_days=318 walk-forward is_size=45 oos_size=34 target_windows=8 units=globex_session_days`
- n_days: `318`
- planted_detected: `None` null_detected: `None`

| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS | n_trades | hitrate | BE | gross | net | N | +OOS | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | mean_reversion | MES | kill | missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,doubt | 0.000 | 0.000 | n/a | 8 | -5.43753e-06 | 41 | 0.000 | 0.471 | -7.5e-05 | -0.00181554 | 13 | 0.000 | 318 |
| vi-mnq-10-0.55 | volume_imbalance | MNQ | kill | missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,doubt | 0.000 | 0.000 | n/a | 8 | -3.89384e-06 | 41 | 0.000 | 0.565 | -0.00012 | -0.00128998 | 14 | 0.000 | 318 |
| rm-mes-10-0.40 | regime_momentum | MES | kill | missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,doubt | 0.000 | 0.000 | n/a | 8 | -4.989e-06 | 41 | 1.000 | 0.471 | 7.5e-05 | -0.00166554 | 15 | 0.000 | 318 |
| or-mes-5-bo | opening_range_breakout | MES | kill | fewer_than_min_oos_windows,walk_forward_windows_below_min,missing_oos_distribution,missing_dsr,missing_pbo,missing_costs,missing_median_oos_after_costs,missing_regimes,purge_or_embargo_missing,trial_registry_empty,trial_count_mismatch,pbo_requires_multiple_configs,static_structural_decay,doubt | n/a | n/a | n/a | 0 | n/a | 0 | nan | 0.471 | 0 | 0 | 16 | nan | 318 |
| or-mnq-15-fade | opening_range_fade | MNQ | kill | fewer_than_min_oos_windows,walk_forward_windows_below_min,missing_oos_distribution,missing_dsr,missing_pbo,missing_costs,missing_median_oos_after_costs,missing_regimes,purge_or_embargo_missing,trial_registry_empty,trial_count_mismatch,pbo_requires_multiple_configs,static_structural_decay,doubt | n/a | n/a | n/a | 0 | n/a | 0 | nan | 0.565 | 0 | 0 | 17 | nan | 318 |
| gap-mes-8 | overnight_gap | MES | kill | fewer_than_min_oos_windows,walk_forward_windows_below_min,missing_oos_distribution,missing_dsr,missing_pbo,missing_costs,missing_median_oos_after_costs,missing_regimes,purge_or_embargo_missing,trial_registry_empty,trial_count_mismatch,pbo_requires_multiple_configs,static_structural_decay,doubt | n/a | n/a | n/a | 0 | n/a | 0 | nan | 0.471 | 0 | 0 | 18 | nan | 318 |
| vwap-mes-20-1.5 | vwap_distance | MES | kill | fewer_than_min_oos_windows,walk_forward_windows_below_min,missing_oos_distribution,missing_dsr,missing_pbo,missing_costs,missing_median_oos_after_costs,missing_regimes,purge_or_embargo_missing,trial_registry_empty,trial_count_mismatch,pbo_requires_multiple_configs,static_structural_decay,doubt | n/a | n/a | n/a | 0 | n/a | 0 | nan | 0.471 | 0 | 0 | 19 | nan | 318 |
| rc-mes-20-0.25 | range_compression | MES | kill | missing_regimes,dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,doubt | 0.000 | 0.000 | n/a | 8 | -4.989e-06 | 40 | 1.000 | 0.471 | 7.3e-05 | -0.00158466 | 20 | 0.000 | 318 |
| cr-mes-3 | close_reversal | MES | kill | fewer_than_min_oos_windows,walk_forward_windows_below_min,missing_oos_distribution,missing_dsr,missing_pbo,missing_costs,missing_median_oos_after_costs,missing_regimes,purge_or_embargo_missing,trial_registry_empty,trial_count_mismatch,pbo_requires_multiple_configs,static_structural_decay,doubt | n/a | n/a | n/a | 0 | n/a | 0 | nan | 0.471 | 0 | 0 | 21 | nan | 318 |
| tod-mes-15 | time_of_day_inventory | MES | kill | fewer_than_min_oos_windows,walk_forward_windows_below_min,missing_oos_distribution,missing_dsr,missing_pbo,missing_costs,missing_median_oos_after_costs,missing_regimes,purge_or_embargo_missing,trial_registry_empty,trial_count_mismatch,pbo_requires_multiple_configs,static_structural_decay,doubt | n/a | n/a | n/a | 0 | n/a | 0 | nan | 0.471 | 0 | 0 | 22 | nan | 318 |
| pb-mnq-20 | trend_pullback | MNQ | kill | fewer_than_min_oos_windows,walk_forward_windows_below_min,missing_oos_distribution,missing_dsr,missing_pbo,missing_costs,missing_median_oos_after_costs,missing_regimes,purge_or_embargo_missing,trial_registry_empty,trial_count_mismatch,pbo_requires_multiple_configs,static_structural_decay,doubt | n/a | n/a | n/a | 0 | n/a | 0 | nan | 0.565 | 0 | 0 | 23 | nan | 318 |
| vx-mes-20 | volatility_expansion | MES | kill | fewer_than_min_oos_windows,walk_forward_windows_below_min,missing_oos_distribution,missing_dsr,missing_pbo,missing_costs,missing_median_oos_after_costs,missing_regimes,purge_or_embargo_missing,trial_registry_empty,trial_count_mismatch,pbo_requires_multiple_configs,static_structural_decay,doubt | n/a | n/a | n/a | 0 | n/a | 0 | nan | 0.471 | 0 | 0 | 24 | nan | 318 |

## Per-config diagnostics (D14)

| config | commission $ | half-spread $ | slippage $ | impact $ | IS Sharpes | OOS Sharpes | volH | volL | trendU | trendD | bootstrap n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | 78.96 | 52.5 | 42 | 0.594 | -9.617,-9.642,-9.642,-10.208,-9.309,-9.822,-10.260,-9.642 | -8.808,-9.550,-10.365,-9.112,-11.055,-10.331,-8.808,-9.112 | -9.808 | -9.680 | -9.759 | nan | 48 |
| vi-mnq-10-0.55 | 78.96 | 21 | 16.8 | 0.2376 | -9.812,-9.870,-9.870,-10.471,-9.810,-10.288,-10.591,-9.870 | -8.978,-9.764,-10.716,-9.688,-11.366,-10.636,-8.978,-9.688 | -10.030 | -10.089 | -10.075 | nan | 48 |
| rm-mes-10-0.40 | 78.96 | 52.5 | 42 | 0.594 | -9.305,-9.279,-9.279,-9.790,-8.532,-9.095,-9.737,-9.279 | -8.534,-9.207,-9.812,-8.222,-10.564,-9.847,-8.534,-8.222 | -9.452 | -9.040 | -9.261 | nan | 48 |
| or-mes-5-bo | 0 | 0 | 0 | 0 | n/a | n/a | nan | nan | nan | nan | 0 |
| or-mnq-15-fade | 0 | 0 | 0 | 0 | n/a | n/a | nan | nan | nan | nan | 0 |
| gap-mes-8 | 0 | 0 | 0 | 0 | n/a | n/a | nan | nan | nan | nan | 0 |
| vwap-mes-20-1.5 | 0 | 0 | 0 | 0 | n/a | n/a | nan | nan | nan | nan | 0 |
| rc-mes-20-0.25 | 75.2 | 50 | 40 | 0.5657 | -7.161,-9.279,-9.279,-9.790,-8.532,-9.095,-9.737,-9.279 | -8.534,-9.207,-9.812,-8.222,-10.564,-9.847,-8.534,-8.222 | -8.846 | -9.040 | -8.957 | nan | 48 |
| cr-mes-3 | 0 | 0 | 0 | 0 | n/a | n/a | nan | nan | nan | nan | 0 |
| tod-mes-15 | 0 | 0 | 0 | 0 | n/a | n/a | nan | nan | nan | nan | 0 |
| pb-mnq-20 | 0 | 0 | 0 | 0 | n/a | n/a | nan | nan | nan | nan | 0 |
| vx-mes-20 | 0 | 0 | 0 | 0 | n/a | n/a | nan | nan | nan | nan | 0 |

## Independent survivors

None.
