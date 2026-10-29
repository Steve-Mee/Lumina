# Phase 5 P2 results (kill / survive)

- generated_at: `2026-10-29T13:43:48.056614+00:00`
- tested: `12` killed: `12` survivors: `0`
- kill_rate: `1.0000`
- holdout_seal: `85e4588fde77159315a72bdaa722d6487f93bbad9bf24999311f893950489d40`
- previous_holdout_seal: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: `n_days=595 walk-forward is_size=42 oos_size=69 target_windows=8 units=globex_session_days`
- n_days: `595`
- planted_detected: `True` null_detected: `False`

| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS | n_trades | hitrate | BE | gross | net | N | +OOS | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | mean_reversion | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.0038498 | 31608 | 0.290 | 0.471 | -0.516437 | -2.50999 | 17 | 0.000 | 600 |
| vi-mnq-10-0.55 | volume_imbalance | MNQ | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.0025119 | 15187 | 0.180 | 0.565 | -0.280025 | -1.45977 | 18 | 0.000 | 595 |
| rm-mes-10-0.40 | regime_momentum | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.00336438 | 28124 | 0.295 | 0.471 | -0.443888 | -2.18738 | 19 | 0.000 | 600 |
| or-mes-5-bo | opening_range_breakout | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.00521618 | 40685 | 0.288 | 0.471 | -0.677713 | -3.48739 | 20 | 0.000 | 600 |
| or-mnq-15-fade | opening_range_fade | MNQ | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.011759 | 75351 | 0.197 | 0.565 | -1.23721 | -7.19687 | 21 | 0.000 | 595 |
| gap-mes-8 | overnight_gap | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -8.04767e-05 | 523 | 0.254 | 0.471 | -0.0126375 | -0.0460109 | 22 | 0.000 | 600 |
| vwap-mes-20-1.5 | vwap_distance | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.00338736 | 28490 | 0.293 | 0.471 | -0.4509 | -2.21647 | 23 | 0.000 | 600 |
| rc-mes-20-0.25 | range_compression | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.00335953 | 25811 | 0.295 | 0.471 | -0.405888 | -2.10675 | 24 | 0.000 | 600 |
| cr-mes-3 | close_reversal | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.00285517 | 22128 | 0.286 | 0.471 | -0.387288 | -1.822 | 25 | 0.000 | 600 |
| tod-mes-15 | time_of_day_inventory | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.000450992 | 2854 | 0.262 | 0.471 | -0.063225 | -0.282026 | 26 | 0.000 | 600 |
| pb-mnq-20 | trend_pullback | MNQ | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.000 | 0.000 | n/a | 8 | -0.00305813 | 19350 | 0.202 | 0.565 | -0.3049 | -1.74183 | 27 | 0.000 | 595 |
| vx-mes-20 | volatility_expansion | MES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.00354135 | 27507 | 0.289 | 0.471 | -0.455875 | -2.23918 | 28 | 0.000 | 600 |

## Per-config diagnostics (D14)

| config | commission $ | half-spread $ | slippage $ | impact $ | IS Sharpes | OOS Sharpes | volH | volL | trendU | trendD | bootstrap n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | 5.942e+04 | 3.951e+04 | 9.813e+04 | 2292 | -33.274,-35.071,-32.579,-36.395,-27.474,-34.946,-33.078,-29.944 | -35.923,-30.941,-32.872,-30.739,-33.666,-20.355,-31.050,-30.907 | -24.490 | -31.076 | -30.377 | -26.581 | 48 |
| vi-mnq-10-0.55 | 2.855e+04 | 7594 | 8.027e+04 | 1555 | -41.514,-40.714,-32.862,-59.258,-35.432,-38.109,-36.445,-38.503 | -40.623,-36.521,-44.081,-38.510,-35.273,-25.853,-40.074,-30.433 | -32.093 | -37.933 | -36.275 | -30.438 | 48 |
| rm-mes-10-0.40 | 5.287e+04 | 3.516e+04 | 8.448e+04 | 1838 | -26.012,-28.863,-13.572,-4.198,-13.960,-13.609,-22.349,-35.422 | -33.446,-18.434,-11.223,-15.214,-11.723,-13.470,-31.059,-16.693 | -10.058 | -28.701 | -19.163 | -10.611 | 48 |
| or-mes-5-bo | 7.649e+04 | 5.086e+04 | 1.506e+05 | 2994 | -29.305,-35.794,-25.261,-26.277,-24.502,-31.155,-29.502,-22.917 | -36.305,-27.760,-22.996,-26.150,-29.035,-16.039,-24.359,-25.394 | -19.651 | -25.877 | -25.662 | -21.525 | 48 |
| or-mnq-15-fade | 1.417e+05 | 3.768e+04 | 4.091e+05 | 7529 | -37.057,-32.219,-35.293,-35.196,-36.495,-43.133,-29.835,-31.657 | -36.582,-33.040,-32.308,-33.826,-37.755,-22.513,-36.117,-24.524 | -28.850 | -32.261 | -31.913 | -27.167 | 48 |
| gap-mes-8 | 983.2 | 653.8 | 1657 | 43.44 | -8.501,-9.354,-5.213,-6.557,-11.190,-12.204,-3.985,-10.975 | -11.832,-5.470,-7.684,-8.289,-12.380,-9.178,-9.645,-12.584 | -10.086 | -9.101 | -9.333 | -10.400 | 48 |
| vwap-mes-20-1.5 | 5.356e+04 | 3.561e+04 | 8.531e+04 | 2067 | -31.724,-30.415,-30.131,-34.672,-29.582,-32.828,-35.730,-31.793 | -32.924,-30.105,-32.239,-32.909,-32.767,-21.434,-31.590,-28.111 | -24.711 | -29.530 | -30.582 | -26.518 | 48 |
| rc-mes-20-0.25 | 4.853e+04 | 3.226e+04 | 8.752e+04 | 1771 | -39.281,-35.647,-30.383,-38.039,-36.968,-37.651,-35.245,-35.301 | -38.012,-34.260,-31.966,-36.516,-37.196,-20.029,-31.280,-28.633 | -26.095 | -32.212 | -33.051 | -26.141 | 48 |
| cr-mes-3 | 4.16e+04 | 2.766e+04 | 7.265e+04 | 1562 | -27.675,-31.990,-31.581,-40.395,-26.943,-32.068,-31.729,-26.890 | -31.994,-32.848,-31.478,-30.096,-29.676,-20.362,-27.945,-28.517 | -24.664 | -29.066 | -29.051 | -26.517 | 48 |
| tod-mes-15 | 5366 | 3568 | 1.275e+04 | 200.4 | -17.757,-14.180,-16.157,-27.591,-20.140,-25.122,-19.321,-19.336 | -14.201,-16.693,-21.080,-17.035,-23.173,-19.491,-18.753,-27.968 | -19.913 | -17.573 | -18.268 | -21.044 | 48 |
| pb-mnq-20 | 3.638e+04 | 9675 | 9.584e+04 | 1797 | -32.339,-36.954,-15.363,nan,-32.023,-17.474,-32.503,-35.837 | -44.080,-21.670,-10.553,-25.371,-14.581,-15.986,-39.392,-18.796 | -12.048 | -47.099 | -25.782 | -11.752 | 48 |
| vx-mes-20 | 5.172e+04 | 3.438e+04 | 9.021e+04 | 2018 | -33.416,-41.927,-29.360,-46.063,-34.101,-35.301,-36.080,-31.141 | -39.663,-30.707,-34.154,-36.669,-35.290,-22.587,-31.132,-30.239 | -28.059 | -31.325 | -32.744 | -29.085 | 48 |

## Independent survivors

None.

## Holdout evaluation

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

