# Phase 5 P2 results (kill / survive)

- generated_at: `2026-10-29T13:43:59.495356+00:00`
- tested: `0` killed: `0` survivors: `0`
- kill_rate: `n/a`
- holdout_seal: `n/a`
- previous_holdout_seal: `n/a`
- windows: `n/a`
- n_days: `0`
- planted_detected: `None` null_detected: `None`

| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS | n_trades | hitrate | BE | gross | net | N | +OOS | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2c-mr-es-10-1.5 | mean_reversion | ES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-vi-nq-10-0.55 | volume_imbalance | NQ | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-rm-es-10-0.40 | regime_momentum | ES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-or-es-5-bo | opening_range_breakout | ES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-or-nq-15-fade | opening_range_fade | NQ | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-gap-es-8 | overnight_gap | ES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-vwap-es-20-1.5 | vwap_distance | ES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-rc-es-20-0.25 | range_compression | ES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-cr-es-3 | close_reversal | ES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-tod-es-15 | time_of_day_inventory | ES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-pb-nq-20 | trend_pullback | NQ | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-vx-es-20 | volatility_expansion | ES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## Per-config diagnostics (D14)

| config | commission $ | half-spread $ | slippage $ | impact $ | IS Sharpes | OOS Sharpes | volH | volL | trendU | trendD | bootstrap n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p2c-mr-es-10-1.5 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-vi-nq-10-0.55 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-rm-es-10-0.40 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-or-es-5-bo | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-or-nq-15-fade | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-gap-es-8 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-vwap-es-20-1.5 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-rc-es-20-0.25 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-cr-es-3 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-tod-es-15 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-pb-nq-20 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| p2c-vx-es-20 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |

## Independent survivors

None.
