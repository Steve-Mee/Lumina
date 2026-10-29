# P2 cost-fix + four-instrument comparison (2026-10-29)

- generated_at: `2026-10-29T14:47:53.907358+00:00`
- cost_model: `1.2.0` (baseline 1.1.0 in phase5_research_cycles.json)
- floors: DSR 0.95, PBO hard 0.50; holdout pin 2026-01-28T23:00:00Z closed
- propose-only; no SIM/REAL orders; Risk Core untouched

## MES/MNQ cost-fix effect (1.1.0 baseline vs 1.2.0 rerun)

Same 12 first-cycle ids. New files only. Same-bar round trips now pay both
commission sides. Session-local ADV + cap 4 changes ETH slippage.

| config | inst | n_trades 1.1.0 | n_trades 1.2.0 | hit 1.1.0 | hit 1.2.0 | BE | gross 1.1.0 | gross 1.2.0 | net 1.1.0 | net 1.2.0 | +OOS 1.1.0 | +OOS 1.2.0 | comm/trade 1.1.0 | comm/trade 1.2.0 | 4leg/trade 1.1.0 | 4leg/trade 1.2.0 | gross/trade 1.1.0 | gross/trade 1.2.0 | death 1.1.0 | death 1.2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | MES | 31628 | 31608 | 0.2902 | 0.2901 | 0.4713 | -0.5158 | -0.5164 | -1.597 | -2.51 | 0 | 0 | 1.158 | 1.88 | 3.42 | 6.307 | -1.631e-05 | -1.634e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| vi-mnq-10-0.55 | MNQ | 15192 | 15187 | 0.1802 | 0.1802 | 0.5653 | -0.28 | -0.28 | -0.3121 | -1.46 | 0 | 0 | 0.08217 | 1.88 | 0.2113 | 7.768 | -1.843e-05 | -1.844e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| rm-mes-10-0.40 | MES | 28135 | 28124 | 0.295 | 0.2949 | 0.4713 | -0.4428 | -0.4439 | -1.512 | -2.187 | 0 | 0 | 1.273 | 1.88 | 3.801 | 6.199 | -1.574e-05 | -1.578e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| or-mes-5-bo | MES | 40698 | 40685 | 0.2883 | 0.2882 | 0.4713 | -0.6775 | -0.6777 | -2.09 | -3.487 | 0 | 0 | 1.108 | 1.88 | 3.472 | 6.906 | -1.665e-05 | -1.666e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| or-mnq-15-fade | MNQ | 75352 | 75351 | 0.1967 | 0.1967 | 0.5653 | -1.237 | -1.237 | -1.425 | -7.197 | 0 | 0 | 0.09239 | 1.88 | 0.2496 | 7.909 | -1.642e-05 | -1.642e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| gap-mes-8 | MES | 533 | 523 | 0.2589 | 0.2543 | 0.4713 | -0.01269 | -0.01264 | -0.02096 | -0.04601 | 0 | 0 | 0.6808 | 1.88 | 1.553 | 6.381 | -2.38e-05 | -2.416e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| vwap-mes-20-1.5 | MES | 28510 | 28490 | 0.2936 | 0.2933 | 0.4713 | -0.449 | -0.4509 | -1.416 | -2.216 | 0 | 0 | 1.166 | 1.88 | 3.392 | 6.197 | -1.575e-05 | -1.583e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| rc-mes-20-0.25 | MES | 25820 | 25811 | 0.2948 | 0.2949 | 0.4713 | -0.4064 | -0.4059 | -1.393 | -2.107 | 0 | 0 | 1.25 | 1.88 | 3.819 | 6.59 | -1.574e-05 | -1.573e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| cr-mes-3 | MES | 22147 | 22128 | 0.2856 | 0.2857 | 0.4713 | -0.3881 | -0.3873 | -1.179 | -1.822 | 0 | 0 | 1.182 | 1.88 | 3.57 | 6.484 | -1.753e-05 | -1.75e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| tod-mes-15 | MES | 2877 | 2854 | 0.2638 | 0.2621 | 0.4713 | -0.06241 | -0.06323 | -0.1371 | -0.282 | 0 | 0 | 0.8867 | 1.88 | 2.595 | 7.666 | -2.169e-05 | -2.215e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| pb-mnq-20 | MNQ | 19354 | 19350 | 0.2021 | 0.2021 | 0.5653 | -0.3049 | -0.3049 | -0.3641 | -1.742 | 0 | 0 | 0.113 | 1.88 | 0.3055 | 7.426 | -1.576e-05 | -1.576e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| vx-mes-20 | MES | 27531 | 27507 | 0.2895 | 0.2895 | 0.4713 | -0.4556 | -0.4559 | -1.375 | -2.239 | 0 | 0 | 1.134 | 1.88 | 3.341 | 6.483 | -1.655e-05 | -1.657e-05 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |

### MES cost-fix effect

- configs: `9` (same 16/8 geometry, CostModel 1.2.0)
- mean commission/trade: `1.093` → `1.88` (ADR-0055 $1.88 RT)
- Gross per trade is almost unchanged. Net worsens because previously skipped
  same-bar commission and mixed-ADV ETH slippage are now charged.
- Verdict stays 9/9 kill. No survivor. Holdout still sealed.

### MNQ cost-fix effect

- configs: `3` (same 16/8 geometry, CostModel 1.2.0)
- mean commission/trade: `0.09584` → `1.88` (was ~10× too cheap vs MES)
- 1.1.0 skipped both $0.94 sides on same-bar 16/8 round trips, which MNQ
  1m ranges hit more often than MES. 1.2.0 charges $1.88 RT whenever the
  fill bar is in-position, matching MES.
- Verdict stays 3/3 kill. No survivor. Holdout still sealed.
- Extra D13 trials: MNQ planted+null ran on this rerun (per-instrument
  control). That adds two registry trials vs the 1.1.0 table; DSR stays 0.

## Four-root table (cost/trade vs gross/trade)

| config | inst | tested | death | n_trades | hit | BE | gross | net | +OOS | median OOS | comm $ | 4leg $ | comm/trade | 4leg/trade | gross/trade |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | MES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 31608 | 0.2901 | 0.4713 | -0.5164 | -2.51 | 0 | -0.00385 | 59424.9 | 199355 | 1.88 | 6.307 | -1.634e-05 |
| vi-mnq-10-0.55 | MNQ | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 15187 | 0.1802 | 0.5653 | -0.28 | -1.46 | 0 | -0.002512 | 28551.6 | 117975 | 1.88 | 7.768 | -1.844e-05 |
| rm-mes-10-0.40 | MES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 28124 | 0.2949 | 0.4713 | -0.4439 | -2.187 | 0 | -0.003364 | 52873.1 | 174349 | 1.88 | 6.199 | -1.578e-05 |
| or-mes-5-bo | MES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 40685 | 0.2882 | 0.4713 | -0.6777 | -3.487 | 0 | -0.005216 | 76491.6 | 280968 | 1.88 | 6.906 | -1.666e-05 |
| or-mnq-15-fade | MNQ | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 75351 | 0.1967 | 0.5653 | -1.237 | -7.197 | 0 | -0.01176 | 141660 | 595966 | 1.88 | 7.909 | -1.642e-05 |
| gap-mes-8 | MES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 523 | 0.2543 | 0.4713 | -0.01264 | -0.04601 | 0 | -8.048e-05 | 983.24 | 3337.34 | 1.88 | 6.381 | -2.416e-05 |
| vwap-mes-20-1.5 | MES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 28490 | 0.2933 | 0.4713 | -0.4509 | -2.216 | 0 | -0.003387 | 53563.1 | 176557 | 1.88 | 6.197 | -1.583e-05 |
| rc-mes-20-0.25 | MES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 25811 | 0.2949 | 0.4713 | -0.4059 | -2.107 | 0 | -0.00336 | 48526.6 | 170086 | 1.88 | 6.59 | -1.573e-05 |
| cr-mes-3 | MES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 22128 | 0.2857 | 0.4713 | -0.3873 | -1.822 | 0 | -0.002855 | 41600.6 | 143471 | 1.88 | 6.484 | -1.75e-05 |
| tod-mes-15 | MES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 2854 | 0.2621 | 0.4713 | -0.06323 | -0.282 | 0 | -0.000451 | 5365.52 | 21880.1 | 1.88 | 7.666 | -2.215e-05 |
| pb-mnq-20 | MNQ | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | 19350 | 0.2021 | 0.5653 | -0.3049 | -1.742 | 0 | -0.003058 | 36378 | 143693 | 1.88 | 7.426 | -1.576e-05 |
| vx-mes-20 | MES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 27507 | 0.2895 | 0.4713 | -0.4559 | -2.239 | 0 | -0.003541 | 51715 | 178330 | 1.88 | 6.483 | -1.657e-05 |
| p2c-mr-es-10-1.5 | ES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 31327 | 0.2888 | 0.4278 | -5.286 | -21.33 | 0 | -0.03255 | 179840 | 1.60434e+06 | 5.741 | 51.21 | -0.0001687 |
| p2c-rm-es-10-0.40 | ES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 27827 | 0.2988 | 0.4278 | -4.136 | -17.77 | 0 | -0.02918 | 159744 | 1.36347e+06 | 5.741 | 49 | -0.0001486 |
| p2c-or-es-5-bo | ES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 40177 | 0.2892 | 0.4278 | -6.536 | -28.96 | 0 | -0.04538 | 230639 | 2.24283e+06 | 5.741 | 55.82 | -0.0001627 |
| p2c-gap-es-8 | ES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 517 | 0.2495 | 0.4278 | -0.1334 | -0.4928 | 0 | -0.0008203 | 2967.58 | 35944 | 5.74 | 69.52 | -0.000258 |
| p2c-vwap-es-20-1.5 | ES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 28209 | 0.2943 | 0.4278 | -4.341 | -18.53 | 0 | -0.02872 | 161943 | 1.41849e+06 | 5.741 | 50.28 | -0.0001539 |
| p2c-rc-es-20-0.25 | ES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 25425 | 0.297 | 0.4278 | -3.858 | -17.13 | 0 | -0.02767 | 145957 | 1.3274e+06 | 5.741 | 52.21 | -0.0001517 |
| p2c-cr-es-3 | ES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 22148 | 0.29 | 0.4278 | -3.655 | -15.24 | 0 | -0.02489 | 127130 | 1.15867e+06 | 5.74 | 52.32 | -0.000165 |
| p2c-tod-es-15 | ES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 2755 | 0.2799 | 0.4278 | -0.4606 | -2.853 | 0 | -0.004609 | 15813.7 | 239261 | 5.74 | 86.85 | -0.0001672 |
| p2c-vx-es-20 | ES | True | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | 27109 | 0.2918 | 0.4278 | -4.397 | -18.75 | 0 | -0.03113 | 155611 | 1.43498e+06 | 5.74 | 52.93 | -0.0001622 |
| p2c-vi-nq-10-0.55 | NQ | False | not_tested_control_failed | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-or-nq-15-fade | NQ | False | not_tested_control_failed | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-pb-nq-20 | NQ | False | not_tested_control_failed | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## Same-family ES vs MES and NQ vs MNQ (16/8, CostModel 1.2.0)

Translations keep lookback/threshold/mode/16/8. Commission card: MES/MNQ $1.88 RT, ES/NQ $5.74 RT. Gaps were not filled from MES.

| family | micro | mini | micro n | mini n | micro hit | mini hit | micro BE | mini BE | micro comm/trade | mini comm/trade | micro 4leg/trade | mini 4leg/trade | micro gross/trade | mini gross/trade | micro net | mini net | micro death | mini death |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mean_reversion | mr-mes-10-1.5 | p2c-mr-es-10-1.5 | 31608 | 31327 | 0.2901 | 0.2888 | 0.4713 | 0.4278 | 1.88 | 5.741 | 6.307 | 51.21 | -1.634e-05 | -0.0001687 | -2.51 | -21.33 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| volume_imbalance | vi-mnq-10-0.55 | p2c-vi-nq-10-0.55 | 15187 | n/a | 0.1802 | n/a | 0.5653 | n/a | 1.88 | n/a | 7.768 | n/a | -1.844e-05 | n/a | -1.46 | n/a | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | not_tested_control_failed |
| regime_momentum | rm-mes-10-0.40 | p2c-rm-es-10-0.40 | 28124 | 27827 | 0.2949 | 0.2988 | 0.4713 | 0.4278 | 1.88 | 5.741 | 6.199 | 49 | -1.578e-05 | -0.0001486 | -2.187 | -17.77 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| opening_range_breakout | or-mes-5-bo | p2c-or-es-5-bo | 40685 | 40177 | 0.2882 | 0.2892 | 0.4713 | 0.4278 | 1.88 | 5.741 | 6.906 | 55.82 | -1.666e-05 | -0.0001627 | -3.487 | -28.96 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| opening_range_fade | or-mnq-15-fade | p2c-or-nq-15-fade | 75351 | n/a | 0.1967 | n/a | 0.5653 | n/a | 1.88 | n/a | 7.909 | n/a | -1.642e-05 | n/a | -7.197 | n/a | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | not_tested_control_failed |
| overnight_gap | gap-mes-8 | p2c-gap-es-8 | 523 | 517 | 0.2543 | 0.2495 | 0.4713 | 0.4278 | 1.88 | 5.74 | 6.381 | 69.52 | -2.416e-05 | -0.000258 | -0.04601 | -0.4928 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| vwap_distance | vwap-mes-20-1.5 | p2c-vwap-es-20-1.5 | 28490 | 28209 | 0.2933 | 0.2943 | 0.4713 | 0.4278 | 1.88 | 5.741 | 6.197 | 50.28 | -1.583e-05 | -0.0001539 | -2.216 | -18.53 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| range_compression | rc-mes-20-0.25 | p2c-rc-es-20-0.25 | 25811 | 25425 | 0.2949 | 0.297 | 0.4713 | 0.4278 | 1.88 | 5.741 | 6.59 | 52.21 | -1.573e-05 | -0.0001517 | -2.107 | -17.13 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| close_reversal | cr-mes-3 | p2c-cr-es-3 | 22128 | 22148 | 0.2857 | 0.29 | 0.4713 | 0.4278 | 1.88 | 5.74 | 6.484 | 52.32 | -1.75e-05 | -0.000165 | -1.822 | -15.24 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| time_of_day_inventory | tod-mes-15 | p2c-tod-es-15 | 2854 | 2755 | 0.2621 | 0.2799 | 0.4713 | 0.4278 | 1.88 | 5.74 | 7.666 | 86.85 | -2.215e-05 | -0.0001672 | -0.282 | -2.853 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| trend_pullback | pb-mnq-20 | p2c-pb-nq-20 | 19350 | n/a | 0.2021 | n/a | 0.5653 | n/a | 1.88 | n/a | 7.426 | n/a | -1.576e-05 | n/a | -1.742 | n/a | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 | not_tested_control_failed |
| volatility_expansion | vx-mes-20 | p2c-vx-es-20 | 27507 | 27109 | 0.2895 | 0.2918 | 0.4713 | 0.4278 | 1.88 | 5.74 | 6.483 | 52.93 | -1.657e-05 | -0.0001622 | -2.239 | -18.75 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |

## ES/NQ data

- discover_data usable (any root on the mount): `True`
- this batch stopped: `False` reason: `(ran)`
- missing roots for this batch: (none)
- planted_detected: `True` null_detected: `False`
- control_note: `Planted edge: at the first RTH bar of each session, the control knows the sign of that session's last-RTH-close minus first-RTH-open (unadjusted). It holds that direction until RTH close (session flatten, C10). Brackets are 1:1 20000/20000 ticks (CME 20% limit-move ceiling; not an 8-tick clip) so a shuffled 50% null is not a 2R artefact. time_stop_bars=2000 cannot fire inside one RTH session. Four-leg costs unchanged. Known size is the session RTH open-to-close move minus costs. | ES: planted detected, null rejected; NQ: FAILED positive control was not detected or the null control looked like an edge`
- needed if fail-closed: PIT NT8 1m continuous unadjusted CSVs at $LUMINA_RESEARCH_DATA_DIR/{ES,NQ}/1m/*.csv (UTF-8 header timestamp,open,high,low,close,volume; UTC ISO-8601 with offset). Hashes are recorded in phase5_p2_es_nq_holdout_seal.json at pin 2026-01-28T23:00:00Z when both tapes exist. Do not invent bars.
- NQ D13: planted was detected (median OOS +0.027, +OOS 1.00, DSR 1.0). The **null** still had median OOS +0.00266 and +OOS 0.75, so it looked like an edge. Stop NQ. No geometry iteration. See `phase5_p2_es_nq_nq_control_fail_2026-10-29.md`.

## ES/NQ tape gaps (not filled)

Holdout pin `2026-01-28T23:00:00Z` stays closed. No MES/MNQ bars were copied.
Detail: `phase5_p2_es_nq_data_gaps_2026-10-29.md`.
- TRAIN (gate uses this): ES missing 2025-07-13/14 and half of 2025-07-15; both roots thin on 2025-11-28.
- HOLDOUT (sealed, unused for ranking): ES 2026-04-22..04-27 and 2026-05-08/11/12.

## Holdout

MES/MNQ seal 85e4588f reused, not rewritten. ES/NQ seal file is `phase5_p2_es_nq_holdout_seal.json` only when PIT tapes exist. Survivors would get one
holdout pass; none are promoted.
