# Phase 5 P2 results (kill / survive)

- generated_at: `2026-10-29T11:49:05.668008+00:00`
- tested: `12` killed: `12` survivors: `0`
- kill_rate: `1.0000`
- holdout_seal: `85e4588fde77159315a72bdaa722d6487f93bbad9bf24999311f893950489d40`
- previous_holdout_seal: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: `n_days=595 walk-forward is_size=42 oos_size=69 target_windows=8 units=globex_session_days`
- n_days: `595`
- planted_detected: `True` null_detected: `False`

| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS | n_trades | hitrate | BE | gross | net | N | +OOS | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | mean_reversion | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.00263713 | 31628 | 0.290 | 0.471 | -0.5158 | -1.59739 | 15 | 0.000 | 600 |
| vi-mnq-10-0.55 | volume_imbalance | MNQ | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.000517525 | 15192 | 0.180 | 0.565 | -0.279985 | -0.312082 | 16 | 0.000 | 595 |
| rm-mes-10-0.40 | regime_momentum | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.00229227 | 28135 | 0.295 | 0.471 | -0.442775 | -1.5122 | 17 | 0.000 | 600 |
| or-mes-5-bo | opening_range_breakout | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.00337228 | 40698 | 0.288 | 0.471 | -0.677513 | -2.09035 | 18 | 0.000 | 600 |
| or-mnq-15-fade | opening_range_fade | MNQ | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.00229597 | 75352 | 0.197 | 0.565 | -1.23713 | -1.42522 | 19 | 0.000 | 595 |
| gap-mes-8 | overnight_gap | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -3.45963e-05 | 533 | 0.259 | 0.471 | -0.0126875 | -0.0209647 | 20 | 0.000 | 600 |
| vwap-mes-20-1.5 | vwap_distance | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.00234867 | 28510 | 0.294 | 0.471 | -0.448963 | -1.41598 | 21 | 0.000 | 600 |
| rc-mes-20-0.25 | range_compression | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.00226806 | 25820 | 0.295 | 0.471 | -0.406438 | -1.39259 | 22 | 0.000 | 600 |
| cr-mes-3 | close_reversal | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.00191566 | 22147 | 0.286 | 0.471 | -0.388138 | -1.17887 | 23 | 0.000 | 600 |
| tod-mes-15 | time_of_day_inventory | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.000227738 | 2877 | 0.264 | 0.471 | -0.0624125 | -0.13706 | 24 | 0.000 | 600 |
| pb-mnq-20 | trend_pullback | MNQ | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.000660522 | 19354 | 0.202 | 0.565 | -0.30494 | -0.364075 | 25 | 0.000 | 595 |
| vx-mes-20 | volatility_expansion | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.0022732 | 27531 | 0.290 | 0.471 | -0.4556 | -1.3754 | 26 | 0.000 | 600 |

## Per-config diagnostics (D14)

| config | commission $ | half-spread $ | slippage $ | impact $ | IS Sharpes | OOS Sharpes | volH | volL | trendU | trendD | bootstrap n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | 3.662e+04 | 2.435e+04 | 4.598e+04 | 1221 | -34.925,-36.700,-38.408,-39.485,-32.995,-45.767,-36.347,-33.946 | -37.074,-33.915,-39.271,-36.497,-44.914,-32.230,-34.819,-36.933 | -36.070 | -35.656 | -35.581 | -37.754 | 48 |
| vi-mnq-10-0.55 | 1248 | 332 | 1588 | 40.94 | -20.333,-28.293,-19.155,-38.144,-22.907,-31.163,-29.319,-28.113 | -25.301,-20.512,-29.624,-24.838,-28.964,-30.612,-27.823,-25.830 | -27.241 | -24.156 | -25.351 | -25.948 | 48 |
| rm-mes-10-0.40 | 3.583e+04 | 2.382e+04 | 4.616e+04 | 1137 | -27.578,-28.382,-14.590,-4.136,-14.974,-16.869,-25.046,-41.110 | -33.302,-19.875,-11.508,-16.192,-13.984,-14.284,-38.186,-20.190 | -11.588 | -34.765 | -21.788 | -11.967 | 48 |
| or-mes-5-bo | 4.509e+04 | 2.998e+04 | 6.471e+04 | 1496 | -32.024,-39.357,-33.557,-39.966,-31.425,-45.946,-35.378,-34.590 | -38.817,-35.458,-34.596,-33.576,-40.634,-37.667,-35.657,-36.531 | -36.428 | -34.138 | -33.936 | -40.770 | 48 |
| or-mnq-15-fade | 6962 | 1852 | 9765 | 230.4 | -33.710,-31.549,-34.735,-34.952,-31.385,-41.787,-24.842,-29.238 | -33.449,-31.390,-31.401,-29.075,-36.545,-27.655,-33.407,-24.933 | -31.136 | -29.793 | -30.774 | -30.081 | 48 |
| gap-mes-8 | 362.8 | 241.2 | 205.2 | 18.48 | -5.445,-7.448,-1.954,-1.285,-7.095,-4.873,0.277,-5.742 | -9.266,-2.225,-2.743,-4.359,-5.107,-2.683,-5.007,-5.846 | -4.140 | -5.323 | -5.131 | -3.449 | 48 |
| vwap-mes-20-1.5 | 3.325e+04 | 2.21e+04 | 4.024e+04 | 1112 | -30.966,-29.828,-33.035,-36.554,-34.640,-31.459,-38.077,-33.309 | -32.178,-32.465,-37.074,-36.041,-33.740,-35.701,-33.974,-30.670 | -33.818 | -32.490 | -33.895 | -33.373 | 48 |
| rc-mes-20-0.25 | 3.227e+04 | 2.146e+04 | 4.386e+04 | 1029 | -40.874,-36.318,-33.513,-45.142,-49.235,-33.838,-36.408,-41.981 | -38.259,-38.501,-38.853,-43.274,-37.771,-36.354,-36.278,-28.853 | -37.593 | -36.073 | -36.809 | -35.952 | 48 |
| cr-mes-3 | 2.617e+04 | 1.74e+04 | 3.465e+04 | 853 | -27.778,-31.546,-32.297,-40.140,-29.034,-31.511,-33.173,-33.270 | -30.992,-33.865,-33.197,-32.727,-31.003,-32.068,-33.968,-32.498 | -33.105 | -31.208 | -31.794 | -33.669 | 48 |
| tod-mes-15 | 2551 | 1696 | 3121 | 96.17 | -13.823,-11.325,-11.572,-16.484,-12.258,-13.916,-12.444,-10.206 | -11.242,-11.231,-14.477,-10.855,-12.326,-12.709,-11.377,-16.030 | -12.499 | -12.671 | -12.933 | -11.522 | 48 |
| pb-mnq-20 | 2186 | 581.5 | 3072 | 73.3 | -23.946,-32.934,-15.373,nan,-26.123,-17.245,-26.143,-28.372 | -33.889,-19.980,-9.858,-21.068,-14.718,-14.588,-29.521,-18.514 | -11.161 | -35.870 | -22.776 | -11.005 | 48 |
| vx-mes-20 | 3.123e+04 | 2.076e+04 | 3.893e+04 | 1053 | -35.153,-37.866,-31.213,-45.924,-44.573,-31.728,-35.890,-35.213 | -35.984,-31.991,-37.377,-42.161,-34.767,-39.066,-34.886,-32.281 | -40.037 | -32.438 | -34.619 | -40.394 | 48 |

## Independent survivors

None.

## Holdout evaluation

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

