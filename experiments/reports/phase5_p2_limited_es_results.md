# Phase 5 P2 results (kill / survive)

- generated_at: `2026-10-29T22:25:38.710737+00:00`
- tested: `6` killed: `6` survivors: `0`
- kill_rate: `1.0000`
- holdout_seal: `b389862f6c45ae5cbc74eca6ead72c3cdcadc89e2017cfb2947466a8789a18f8`
- previous_holdout_seal: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: `n_days=598 walk-forward is_size=45 oos_size=69 target_windows=8 units=globex_session_days`
- n_days: `598`
- planted_detected: `True` null_detected: `False`

| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS | n_trades | hitrate | BE | gross | net | N | +OOS | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2l-mr-es | mean_reversion | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.343 | 0.000 | n/a | 8 | -0.00191032 | 734 | 0.484 | 0.545 | -0.352101 | -0.739593 | 73 | 0.125 | 598 |
| p2l-or-fade-es | opening_range_fade | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.343 | 0.000 | n/a | 8 | -0.00159161 | 695 | 0.463 | 0.545 | -0.85704 | -1.1569 | 74 | 0.000 | 598 |
| p2l-vwap-es | vwap_distance | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.343 | 0.000 | n/a | 8 | -0.00159753 | 729 | 0.486 | 0.545 | -0.602953 | -0.9777 | 75 | 0.125 | 598 |
| p2l-tod-es | time_of_day_inventory | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.343 | 0.002 | n/a | 8 | -0.000575695 | 589 | 0.494 | 0.545 | 0.0997857 | -0.206213 | 76 | 0.375 | 598 |
| p2l-rc-es | range_compression | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.343 | 0.000 | n/a | 8 | -0.000841178 | 682 | 0.509 | 0.333 | -0.108541 | -0.432397 | 77 | 0.125 | 598 |
| p2l-vx-es | volatility_expansion | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.343 | 0.000 | n/a | 8 | -0.00135464 | 732 | 0.489 | 0.333 | -0.486223 | -0.86474 | 78 | 0.250 | 598 |

## Per-config diagnostics (D14)

| config | commission $ | half-spread $ | slippage $ | impact $ | IS Sharpes | OOS Sharpes | volH | volL | trendU | trendD | bootstrap n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p2l-mr-es | 4265 | 9288 | 2.468e+04 | 513.5 | -0.493,0.971,-0.096,4.482,-2.977,-3.589,0.142,-1.202 | -0.814,-1.873,2.617,-3.077,-0.231,-1.254,-1.925,-1.951 | -0.725 | -1.453 | -0.883 | -1.144 | 48 |
| p2l-or-fade-es | 4029 | 8775 | 1.669e+04 | 494.7 | -2.234,-4.158,-0.049,-1.721,-3.203,-4.165,2.250,-1.713 | -3.769,-1.254,-1.648,-1.631,-3.533,-0.257,-1.490,-1.214 | -1.681 | -1.595 | -0.815 | -2.923 | 48 |
| p2l-vwap-es | 4236 | 9225 | 2.351e+04 | 508.3 | -1.445,0.324,0.897,4.041,-2.777,-3.136,0.082,-1.401 | -0.025,-1.376,2.046,-1.822,-0.943,-1.699,-1.528,-3.770 | -1.280 | -1.389 | -1.152 | -1.650 | 48 |
| p2l-tod-es | 3427 | 7462 | 1.933e+04 | 383.3 | -2.216,2.180,0.454,1.980,-2.920,1.339,-1.839,-0.332 | 1.630,-0.638,0.322,-0.635,2.657,-1.481,-2.504,-0.894 | -0.035 | -0.773 | -0.978 | 0.790 | 48 |
| p2l-rc-es | 3961 | 8625 | 1.935e+04 | 445.4 | -0.523,-1.709,2.742,-1.370,2.241,-2.354,-1.441,-4.468 | -1.947,3.695,-0.006,-0.167,-1.808,-1.300,-2.123,-0.181 | -0.854 | -0.123 | -0.283 | -1.113 | 48 |
| p2l-vx-es | 4253 | 9262 | 2.38e+04 | 537.8 | -0.104,-1.643,0.523,-4.735,-0.802,1.235,-0.528,-3.788 | -2.358,0.700,-2.576,-1.689,-0.645,-3.257,-0.799,1.360 | -1.354 | -1.002 | -1.273 | -1.212 | 48 |

## Exit / MFE / unbracketed / 1R (not extra trials)

| config | ATR tgt | ATR stop | no-bracket | time_stop_bars | stop | target | time_stop | session_end | mean MFE ticks | mean MAE ticks | hitrate N=16 | hitrate N=60 | hitrate N=120 | hitrate 1R/1R | gross ticks | net ticks | gross pts | net pts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2l-mr-es | 1.00 | 1.20 | False | 2000 | 59 | 85 | 0 | 590 | 97.339 | 103.454 | 0.463 | 0.488 | 0.489 | 0.487 | -3067.809 | -6167.741 | -767 | -1542 |
| p2l-or-fade-es | 1.00 | 1.20 | False | 2000 | 49 | 58 | 0 | 588 | 84.030 | 98.511 | 0.463 | 0.483 | 0.478 | 0.458 | -6923.317 | -9322.166 | -1731 | -2331 |
| p2l-vwap-es | 1.00 | 1.20 | False | 2000 | 64 | 75 | 0 | 590 | 94.886 | 103.767 | 0.467 | 0.481 | 0.483 | 0.490 | -4946.621 | -7944.599 | -1237 | -1986 |
| p2l-tod-es | 1.00 | 1.20 | False | 2000 | 41 | 75 | 0 | 473 | 101.808 | 101.374 | 0.502 | 0.507 | 0.520 | 0.491 | 801.286 | -1646.704 | 200.3 | -411.7 |
| p2l-rc-es | 1.80 | 0.90 | False | 2000 | 81 | 12 | 0 | 589 | 96.651 | 90.742 | 0.476 | 0.476 | 0.495 | 0.525 | -838.325 | -3429.179 | -209.6 | -857.3 |
| p2l-vx-es | 1.80 | 0.90 | False | 2000 | 124 | 17 | 0 | 591 | 102.649 | 98.456 | 0.471 | 0.483 | 0.484 | 0.500 | -3963.787 | -6991.923 | -990.9 | -1748 |

## Independent survivors

None.

## Holdout evaluation

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

