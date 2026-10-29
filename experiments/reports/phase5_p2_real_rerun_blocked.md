# Real NT8 12-template re-run blocked

`LUMINA_RESEARCH_DATA_DIR` is unset and the NT8 CSVs are not in git. The sealed holdout was not opened. Re-run on the same 12 templates as soon as `MES_continuous_unadj_1m_2023-10-01_2026-10-29.csv` and the MNQ counterpart are mounted.

# Phase 5 P2 results (kill / survive)

- generated_at: `2026-10-29T10:58:02.770924+00:00`
- tested: `0` killed: `0` survivors: `0`
- kill_rate: `n/a`
- holdout_seal: `n/a`
- previous_holdout_seal: `n/a`
- windows: `n/a`
- n_days: `0`
- planted_detected: `None` null_detected: `None`

| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS | n_trades | hitrate | BE | gross | net | N | +OOS | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | mean_reversion | MES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| vi-mnq-10-0.55 | volume_imbalance | MNQ | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| rm-mes-10-0.40 | regime_momentum | MES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| or-mes-5-bo | opening_range_breakout | MES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| or-mnq-15-fade | opening_range_fade | MNQ | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| gap-mes-8 | overnight_gap | MES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| vwap-mes-20-1.5 | vwap_distance | MES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| rc-mes-20-0.25 | range_compression | MES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| cr-mes-3 | close_reversal | MES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| tod-mes-15 | time_of_day_inventory | MES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| pb-mnq-20 | trend_pullback | MNQ | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| vx-mes-20 | volatility_expansion | MES | untested | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## Per-config diagnostics (D14)

| config | commission $ | half-spread $ | slippage $ | impact $ | IS Sharpes | OOS Sharpes | volH | volL | trendU | trendD | bootstrap n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| vi-mnq-10-0.55 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| rm-mes-10-0.40 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| or-mes-5-bo | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| or-mnq-15-fade | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| gap-mes-8 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| vwap-mes-20-1.5 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| rc-mes-20-0.25 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| cr-mes-3 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| tod-mes-15 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| pb-mnq-20 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |
| vx-mes-20 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 0 |

## Independent survivors

None.
