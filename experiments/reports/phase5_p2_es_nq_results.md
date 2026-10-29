# Phase 5 P2 results (kill / survive)

- generated_at: `2026-10-29T14:47:53.904405+00:00`
- tested: `9` killed: `9` survivors: `0`
- kill_rate: `1.0000`
- holdout_seal: `454b8d1f7fd8b0fe0ee43b9c4431515be3912e4859a6a268372ec1c3aff5abd4`
- previous_holdout_seal: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: `n_days=599 walk-forward is_size=46 oos_size=69 target_windows=8 units=globex_session_days`
- n_days: `599`
- planted_detected: `True` null_detected: `False`

| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS | n_trades | hitrate | BE | gross | net | N | +OOS | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2c-mr-es-10-1.5 | mean_reversion | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.0325501 | 31327 | 0.289 | 0.428 | -5.28575 | -21.3291 | 14 | 0.000 | 599 |
| p2c-rm-es-10-0.40 | regime_momentum | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.0291821 | 27827 | 0.299 | 0.428 | -4.136 | -17.7707 | 15 | 0.000 | 599 |
| p2c-or-es-5-bo | opening_range_breakout | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.0453799 | 40177 | 0.289 | 0.428 | -6.53563 | -28.9639 | 16 | 0.000 | 599 |
| p2c-gap-es-8 | overnight_gap | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.000820287 | 517 | 0.250 | 0.428 | -0.133375 | -0.492815 | 17 | 0.000 | 599 |
| p2c-vwap-es-20-1.5 | vwap_distance | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.0287248 | 28209 | 0.294 | 0.428 | -4.3405 | -18.5254 | 18 | 0.000 | 599 |
| p2c-rc-es-20-0.25 | range_compression | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.0276673 | 25425 | 0.297 | 0.428 | -3.85763 | -17.1316 | 19 | 0.000 | 599 |
| p2c-cr-es-3 | close_reversal | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.0248922 | 22148 | 0.290 | 0.428 | -3.6555 | -15.2422 | 20 | 0.000 | 599 |
| p2c-tod-es-15 | time_of_day_inventory | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.0046093 | 2755 | 0.280 | 0.428 | -0.460625 | -2.85323 | 21 | 0.000 | 599 |
| p2c-vx-es-20 | volatility_expansion | ES | kill | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.000 | 0.000 | n/a | 8 | -0.0311259 | 27109 | 0.292 | 0.428 | -4.3975 | -18.7473 | 22 | 0.000 | 599 |
| p2c-vi-nq-10-0.55 | volume_imbalance | NQ | untested | not_tested_control_failed | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-or-nq-15-fade | opening_range_fade | NQ | untested | not_tested_control_failed | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-pb-nq-20 | trend_pullback | NQ | untested | not_tested_control_failed | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## Per-config diagnostics (D14)

| config | commission $ | half-spread $ | slippage $ | impact $ | IS Sharpes | OOS Sharpes | volH | volL | trendU | trendD | bootstrap n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p2c-mr-es-10-1.5 | 1.798e+05 | 3.916e+05 | 1.013e+06 | 1.939e+04 | -34.392,-28.292,-35.500,-33.781,-23.369,-22.756,-29.126,-27.465 | -28.933,-32.220,-29.825,-26.119,-21.795,-21.803,-26.709,-28.169 | -22.426 | -27.644 | -27.612 | -24.202 | 48 |
| p2c-rm-es-10-0.40 | 1.597e+05 | 3.479e+05 | 8.406e+05 | 1.525e+04 | -24.763,-27.226,-12.805,-4.003,-13.496,-12.448,-21.629,-21.438 | -29.049,-16.225,-9.784,-15.349,-11.580,-14.285,-21.421,-16.657 | -9.891 | -26.309 | -17.873 | -10.541 | 48 |
| p2c-or-es-5-bo | 2.306e+05 | 5.023e+05 | 1.484e+06 | 2.572e+04 | -28.266,-31.841,-25.016,-25.361,-22.264,-19.106,-28.499,-19.984 | -30.468,-26.114,-22.748,-23.149,-18.131,-16.221,-20.680,-23.391 | -17.758 | -24.351 | -23.771 | -19.417 | 48 |
| p2c-gap-es-8 | 2968 | 6462 | 2.623e+04 | 288.7 | -7.766,-7.925,-5.773,-7.915,-11.930,-18.687,-6.314,-12.942 | -9.460,-6.466,-8.089,-9.474,-15.679,-9.714,-11.369,-12.711 | -10.901 | -9.216 | -9.456 | -11.981 | 48 |
| p2c-vwap-es-20-1.5 | 1.619e+05 | 3.527e+05 | 8.864e+05 | 1.745e+04 | -31.023,-26.617,-29.802,-29.711,-26.837,-23.524,-30.555,-29.542 | -26.239,-27.615,-28.850,-28.626,-22.578,-21.671,-26.759,-26.360 | -22.368 | -26.226 | -27.086 | -24.417 | 48 |
| p2c-rc-es-20-0.25 | 1.46e+05 | 3.178e+05 | 8.485e+05 | 1.506e+04 | -32.374,-36.659,-24.592,-32.495,-30.084,-22.980,-30.608,-26.839 | -37.836,-25.773,-27.431,-31.026,-21.555,-18.405,-25.555,-25.352 | -22.908 | -27.055 | -28.572 | -22.996 | 48 |
| p2c-cr-es-3 | 1.271e+05 | 2.768e+05 | 7.413e+05 | 1.339e+04 | -30.243,-28.302,-35.931,-35.482,-24.845,-22.221,-31.278,-22.869 | -26.553,-31.163,-29.752,-26.845,-20.716,-21.367,-24.602,-25.926 | -22.478 | -25.896 | -26.775 | -23.855 | 48 |
| p2c-tod-es-15 | 1.581e+04 | 3.444e+04 | 1.876e+05 | 1373 | -21.818,-12.249,-13.869,-22.380,-16.228,-19.887,-19.372,-21.329 | -12.703,-14.573,-17.202,-15.690,-19.146,-16.914,-19.422,-26.227 | -17.652 | -16.237 | -17.051 | -18.809 | 48 |
| p2c-vx-es-20 | 1.556e+05 | 3.389e+05 | 9.237e+05 | 1.679e+04 | -29.691,-36.194,-23.145,-37.134,-30.996,-25.306,-29.559,-27.627 | -37.831,-25.735,-30.191,-32.648,-24.421,-21.337,-28.578,-28.744 | -25.325 | -28.687 | -28.858 | -26.182 | 48 |
| p2c-vi-nq-10-0.55 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-or-nq-15-fade | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-pb-nq-20 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |

## Independent survivors

None.

## Holdout evaluation

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

