# Phase 5 P2 results (kill / survive)

> **Control-note correction (not a rerun).** D13 used **1:1 1.5×ATR14**, not
> 20000/20000. The BE column `1.634` is the 1/1-tick placeholder from
> `require_geometry(target_ticks=1, stop_ticks=1)`, not an ATR break-even.
> JSON is the untouched PIT dump. See `phase5_p2_atr_es_control_note.md`.
>

- generated_at: `2026-10-29T15:56:28.034609+00:00`
- tested: `10` killed: `10` survivors: `0`
- kill_rate: `1.0000`
- holdout_seal: `cdf964b6413985726a14b7d63375fef9fda52b9a39bedb512ecd43b73b1f8279`
- previous_holdout_seal: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: `n_days=598 walk-forward is_size=45 oos_size=69 target_windows=8 units=globex_session_days`
- n_days: `598`
- planted_detected: `True` null_detected: `False`

| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS | n_trades | hitrate | BE | gross | net | N | +OOS | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2a-mr-es | mean_reversion | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.200 | 0.000 | n/a | 8 | -0.00191032 | 734 | 0.484 | 1.634 | -0.352101 | -0.739593 | 77 | 0.125 | 598 |
| p2a-vwap-es | vwap_distance | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.200 | 0.000 | n/a | 8 | -0.00159753 | 729 | 0.486 | 1.634 | -0.602953 | -0.9777 | 78 | 0.125 | 598 |
| p2a-tod-es | time_of_day_inventory | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.200 | 0.002 | n/a | 8 | -0.000575695 | 589 | 0.494 | 1.634 | 0.0997857 | -0.206213 | 79 | 0.375 | 598 |
| p2a-or-fade-es | opening_range_fade | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.200 | 0.000 | n/a | 8 | -0.00159161 | 695 | 0.463 | 1.634 | -0.85704 | -1.1569 | 80 | 0.000 | 598 |
| p2a-or-bo-es | opening_range_breakout | ES | kill | dsr_below_threshold | 0.200 | 0.057 | n/a | 8 | 0.000534888 | 679 | 0.517 | 1.634 | 0.668168 | 0.384255 | 81 | 0.625 | 598 |
| p2a-rm-es | regime_momentum | ES | kill | dsr_below_threshold | 0.200 | 0.097 | n/a | 8 | 0.00090075 | 510 | 0.524 | 1.634 | 0.631637 | 0.405492 | 82 | 0.625 | 598 |
| p2a-rc-es | range_compression | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.200 | 0.000 | n/a | 8 | -0.000841178 | 682 | 0.509 | 1.634 | -0.108541 | -0.432397 | 83 | 0.125 | 598 |
| p2a-vx-es | volatility_expansion | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.200 | 0.000 | n/a | 8 | -0.00135464 | 732 | 0.489 | 1.634 | -0.486223 | -0.86474 | 84 | 0.250 | 598 |
| p2a-pb-es | trend_pullback | ES | kill | dsr_below_threshold | 0.200 | 0.049 | n/a | 8 | 0.000664623 | 462 | 0.519 | 1.634 | 0.449224 | 0.253856 | 85 | 0.625 | 598 |
| p2a-gap-es | overnight_gap | ES | kill | dsr_below_threshold | 0.200 | 0.019 | n/a | 8 | 0.0011805 | 511 | 0.521 | 1.634 | 0.446 | 0.204871 | 86 | 0.625 | 598 |

## Per-config diagnostics (D14)

| config | commission $ | half-spread $ | slippage $ | impact $ | IS Sharpes | OOS Sharpes | volH | volL | trendU | trendD | bootstrap n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p2a-mr-es | 4265 | 9288 | 2.468e+04 | 513.5 | -0.493,0.971,-0.096,4.482,-2.977,-3.589,0.142,-1.202 | -0.814,-1.873,2.617,-3.077,-0.231,-1.254,-1.925,-1.951 | -0.725 | -1.453 | -0.883 | -1.144 | 48 |
| p2a-vwap-es | 4236 | 9225 | 2.351e+04 | 508.3 | -1.445,0.324,0.897,4.041,-2.777,-3.136,0.082,-1.401 | -0.025,-1.376,2.046,-1.822,-0.943,-1.699,-1.528,-3.770 | -1.280 | -1.389 | -1.152 | -1.650 | 48 |
| p2a-tod-es | 3427 | 7462 | 1.933e+04 | 383.3 | -2.216,2.180,0.454,1.980,-2.920,1.339,-1.839,-0.332 | 1.630,-0.638,0.322,-0.635,2.657,-1.481,-2.504,-0.894 | -0.035 | -0.773 | -0.978 | 0.790 | 48 |
| p2a-or-fade-es | 4029 | 8775 | 1.669e+04 | 494.7 | -2.234,-4.158,-0.049,-1.721,-3.203,-4.165,2.250,-1.713 | -3.769,-1.254,-1.648,-1.631,-3.533,-0.257,-1.490,-1.214 | -1.681 | -1.595 | -0.815 | -2.923 | 48 |
| p2a-or-bo-es | 3938 | 8575 | 1.54e+04 | 474.8 | 2.938,0.989,-0.187,-0.404,2.424,2.995,-2.806,0.595 | 1.523,0.528,-0.147,0.786,2.219,-0.432,0.482,-0.574 | 0.955 | -0.124 | -0.227 | 1.812 | 48 |
| p2a-rm-es | 2950 | 6425 | 1.292e+04 | 321.9 | -1.363,-4.626,-1.053,3.234,4.015,1.812,-0.983,-1.639 | -2.101,-0.476,3.583,2.758,2.632,-1.419,0.062,2.353 | 1.770 | -0.246 | 0.222 | 2.380 | 48 |
| p2a-rc-es | 3961 | 8625 | 1.935e+04 | 445.4 | -0.523,-1.709,2.742,-1.370,2.241,-2.354,-1.441,-4.468 | -1.947,3.695,-0.006,-0.167,-1.808,-1.300,-2.123,-0.181 | -0.854 | -0.123 | -0.283 | -1.113 | 48 |
| p2a-vx-es | 4253 | 9262 | 2.38e+04 | 537.8 | -0.104,-1.643,0.523,-4.735,-0.802,1.235,-0.528,-3.788 | -2.358,0.700,-2.576,-1.689,-0.645,-3.257,-0.799,1.360 | -1.354 | -1.002 | -1.273 | -1.212 | 48 |
| p2a-pb-es | 2675 | 5825 | 1.076e+04 | 275.5 | -0.185,0.010,-1.636,3.918,-0.228,0.970,-2.604,-1.936 | 1.053,-0.894,2.412,-0.765,2.058,-2.629,0.689,2.151 | 1.360 | -0.225 | 0.047 | 1.799 | 48 |
| p2a-gap-es | 2968 | 6462 | 1.435e+04 | 329.7 | -0.785,-6.070,-0.924,-2.346,-2.320,-1.182,1.583,2.358 | -6.095,1.338,-1.989,-2.057,0.739,2.537,1.607,1.375 | 0.947 | -1.220 | -0.211 | 0.917 | 48 |

## Exit / MFE / unbracketed / 1R (not extra trials)

| config | ATR tgt | ATR stop | no-bracket | time_stop_bars | stop | target | time_stop | session_end | mean MFE ticks | mean MAE ticks | hitrate N=60 | hitrate 1R/1R | gross ticks | net ticks | gross pts | net pts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2a-mr-es | 1.00 | 1.20 | False | 2000 | 59 | 85 | 0 | 590 | 97.339 | 103.454 | 0.488 | 0.487 | -3067.809 | -6167.741 | -767 | -1542 |
| p2a-vwap-es | 1.00 | 1.20 | False | 2000 | 64 | 75 | 0 | 590 | 94.886 | 103.767 | 0.481 | 0.490 | -4946.621 | -7944.599 | -1237 | -1986 |
| p2a-tod-es | 1.00 | 1.20 | False | 2000 | 41 | 75 | 0 | 473 | 101.808 | 101.374 | 0.507 | 0.491 | 801.286 | -1646.704 | 200.3 | -411.7 |
| p2a-or-fade-es | 1.00 | 1.20 | False | 2000 | 49 | 58 | 0 | 588 | 84.030 | 98.511 | 0.483 | 0.458 | -6923.317 | -9322.166 | -1731 | -2331 |
| p2a-or-bo-es | 1.80 | 0.90 | False | 2000 | 74 | 16 | 0 | 589 | 101.873 | 83.857 | 0.496 | 0.515 | 5412.343 | 3141.040 | 1353 | 785.3 |
| p2a-rm-es | 1.80 | 0.90 | False | 2000 | 73 | 15 | 0 | 422 | 94.961 | 80.194 | 0.496 | 0.512 | 5028.098 | 3218.934 | 1257 | 804.7 |
| p2a-rc-es | 1.80 | 0.90 | False | 2000 | 81 | 12 | 0 | 589 | 96.651 | 90.742 | 0.476 | 0.525 | -838.325 | -3429.179 | -209.6 | -857.3 |
| p2a-vx-es | 1.80 | 0.90 | False | 2000 | 124 | 17 | 0 | 591 | 102.649 | 98.456 | 0.483 | 0.500 | -3963.787 | -6991.923 | -990.9 | -1748 |
| p2a-pb-es | 1.80 | 0.90 | False | 2000 | 56 | 6 | 0 | 400 | 89.273 | 76.102 | 0.483 | 0.525 | 3504.793 | 1941.849 | 876.2 | 485.5 |
| p2a-gap-es | n/a | n/a | True | 2000 | 0 | 0 | 0 | 511 | 122.470 | 110.198 | 0.489 | nan | 3661.000 | 1731.969 | 915.2 | 433 |

## Independent survivors

None.

## Holdout evaluation

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

