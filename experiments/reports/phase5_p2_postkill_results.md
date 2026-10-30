# Phase 5 P2 results (kill / survive)

- generated_at: `2026-10-30T07:18:10.184375+00:00`
- tested: `3` killed: `3` survivors: `0`
- kill_rate: `1.0000`
- holdout_seal: `91b75a39f2e11e4c8835a348b06471f54289a4152342fdaa71ca8c3ea22f3a47`
- previous_holdout_seal: `6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b`
- windows: `n_days=598 walk-forward is_size=45 oos_size=69 target_windows=8 units=globex_session_days`
- n_days: `598`
- planted_detected: `True` null_detected: `False`

| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS | n_trades | hitrate | BE | gross | net | N | +OOS | n_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2p-rc-es | range_compression | ES | kill | pbo_hard_reject,dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.686 | 0.000 | n/a | 8 | -0.000835308 | 676 | 0.510 | 0.273 | -0.0303585 | -0.35033 | 148 | 0.250 | 598 |
| p2p-vx-es | volatility_expansion | ES | kill | pbo_hard_reject,dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 0.686 | 0.002 | n/a | 8 | -0.000530186 | 719 | 0.499 | 0.273 | 0.230361 | -0.129169 | 149 | 0.500 | 598 |
| p2p-tod-es | time_of_day_inventory | ES | kill | pbo_hard_reject,dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 0.686 | 0.000 | n/a | 8 | -0.000575695 | 594 | 0.492 | 0.545 | 0.0383571 | -0.274804 | 150 | 0.375 | 598 |

## Per-config diagnostics (D14)

| config | commission $ | half-spread $ | slippage $ | impact $ | IS Sharpes | OOS Sharpes | volH | volL | trendU | trendD | bootstrap n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p2p-rc-es | 3926 | 8550 | 1.908e+04 | 440.5 | -0.978,-1.709,2.742,-1.370,2.584,-2.250,-1.441,-4.468 | -1.927,3.800,-0.041,0.217,-1.735,-0.946,-2.009,-0.181 | -0.661 | -0.096 | -0.233 | -0.843 | 48 |
| p2p-vx-es | 4179 | 9100 | 2.217e+04 | 506.6 | -0.104,-1.643,0.822,-4.735,-0.732,1.740,-0.528,-1.309 | -2.362,1.406,-2.909,-1.645,1.545,-0.825,0.453,1.360 | 0.199 | -0.946 | -1.243 | 1.108 | 48 |
| p2p-tod-es | 3461 | 7538 | 1.993e+04 | 392.1 | -2.216,2.180,0.454,2.294,-2.920,0.892,-1.839,-0.512 | 1.630,-0.638,0.511,-0.635,1.782,-1.481,-2.333,-0.894 | -0.172 | -0.837 | -0.998 | 0.554 | 48 |

## Exit / MFE / unbracketed / 1R (not extra trials)

| config | ATR tgt | ATR stop | no-bracket | time_stop_bars | stop | target | time_stop | session_end | mean MFE ticks | mean MAE ticks | hitrate N=16 | hitrate N=60 | hitrate N=120 | hitrate 1R/1R | gross ticks | net ticks | gross pts | net pts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2p-rc-es | 2.40 | 0.90 | False | 2000 | 81 | 6 | 0 | 589 | 97.580 | 91.099 | 0.476 | 0.476 | 0.495 | 0.525 | -212.868 | -2772.641 | -53.22 | -693.2 |
| p2p-vx-es | 2.40 | 0.90 | False | 2000 | 116 | 9 | 0 | 594 | 106.209 | 95.818 | 0.471 | 0.483 | 0.484 | 0.500 | 1768.885 | -1107.348 | 442.2 | -276.8 |
| p2p-tod-es | 1.00 | 1.20 | False | 2000 | 43 | 76 | 0 | 475 | 102.116 | 102.165 | 0.496 | 0.507 | 0.520 | 0.488 | 183.857 | -2321.436 | 45.96 | -580.4 |

## Independent survivors

None.

## Holdout evaluation

Skipped: no independent survivors. The sealed window was not used for ranking or calibration.

