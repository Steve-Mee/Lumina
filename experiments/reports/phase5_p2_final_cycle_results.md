# Phase 5 P2 results (kill / survive)

- generated_at: `2026-10-30T09:37:01.495013+00:00`
- tested: `4` killed: `4` survivors: `0`
- kill_rate: `1.0000`
- holdout_seal: `c17138994a7fa198d27f829a618bdd459552cd3571382c95a8f64f54c88b8c07`
- previous_holdout_seal: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: `n_days=598 walk-forward is_size=45 oos_size=69 target_windows=8 units=globex_session_days`
- n_days: `598`
- planted_detected: `True` null_detected: `False`

| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS | n_trades | hitrate | BE | gross | net | N | +OOS | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2s-rv-01 | mean_reversion | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.357 | 0.000 | n/a | 8 | -0.000292492 | 286 | 0.462 | n/a | -0.00455 | -0.173513 | 71 | 0.250 | 598 |
| p2s-rv-02 | overnight_gap | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.357 | 0.008 | n/a | 8 | -4.99231e-06 | 52 | 0.635 | 1.634 | 0.18675 | 0.000724918 | 72 | 0.500 | 598 |
| p2s-lh-01 | range_compression | ES | kill | dsr_below_threshold,static_positive_share_below_60 | 0.357 | 0.039 | n/a | 8 | 7.4478e-05 | 90 | 0.489 | 0.400 | 0.12325 | 0.083856 | 73 | 0.500 | 598 |
| p2s-lh-03 | close_reversal | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.357 | 0.000 | n/a | 8 | -7.28027e-05 | 59 | 0.627 | 0.750 | -0.04325 | -0.0776521 | 74 | 0.500 | 598 |

## Per-config diagnostics (D14)

| config | commission $ | half-spread $ | slippage $ | impact $ | IS Sharpes | OOS Sharpes | volH | volL | trendU | trendD | bootstrap n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p2s-rv-01 | 1091 | 1662 | 1.395e+04 | 188.2 | -2.717,3.288,-2.996,-0.664,-2.417,1.495,-2.782,-0.162 | 3.161,-2.194,-1.428,-1.523,1.778,-2.244,-0.455,-2.839 | -0.448 | -1.152 | -0.960 | -0.555 | 48 |
| p2s-rv-02 | 585.5 | 892.5 | 1.702e+04 | 109.2 | -2.366,1.262,-0.258,-1.062,-2.993,-2.392,3.369,0.841 | 1.022,0.607,-0.826,-0.741,-0.386,-0.694,0.681,1.730 | -0.673 | 1.189 | 1.050 | -2.234 | 48 |
| p2s-lh-01 | 522.3 | 1138 | 2206 | 73.66 | -3.161,2.184,-0.667,1.990,-4.203,2.986,-2.613,-3.333 | 3.466,-1.076,1.765,-2.300,2.989,-1.234,-4.024,4.171 | 0.684 | -0.057 | -1.054 | 3.506 | 48 |
| p2s-lh-03 | 338.7 | 737.5 | 2302 | 62.01 | -2.406,-1.545,0.220,1.700,-3.145,3.787,-0.151,3.886 | -2.298,0.242,1.424,-3.573,1.700,-1.012,3.666,-2.036 | -0.957 | -0.884 | -1.422 | 0.969 | 48 |

## Exit / MFE / unbracketed / 1R (not extra trials)

| config | ATR tgt | ATR stop | no-bracket | time_stop_bars | stop | target | time_stop | session_end | mean MFE ticks | mean MAE ticks | hitrate N=16 | hitrate N=60 | hitrate N=120 | hitrate 1R/1R | gross ticks | net ticks | gross pts | net pts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2s-rv-01 | n/a | n/a | True | 360 | 207 | 0 | 76 | 0 | 0.000 | 0.000 | n/a | n/a | n/a | n/a | -36.400 | -1388.100 | -9.1 | -347 |
| p2s-rv-02 | n/a | n/a | False | 90 | 14 | 20 | 18 | 0 | 0.000 | 0.000 | n/a | n/a | n/a | n/a | 1494.000 | 5.799 | 373.5 | 1.45 |
| p2s-lh-01 | 1.50 | 1.00 | False | 2000 | 27 | 13 | 0 | 50 | 83.678 | 69.956 | n/a | n/a | n/a | n/a | 992.000 | 676.848 | 248 | 169.2 |
| p2s-lh-03 | 0.50 | 1.50 | False | 90 | 13 | 35 | 11 | 0 | 31.763 | 46.424 | n/a | n/a | n/a | n/a | -346.000 | -621.217 | -86.5 | -155.3 |

## Independent survivors

None.

## Holdout evaluation

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

