# P2 cost-fix + four-instrument comparison (2026-10-29)

- generated_at: `2026-10-29T13:47:51.810738+00:00`
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
| p2c-mr-es-10-1.5 | ES | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-vi-nq-10-0.55 | NQ | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-rm-es-10-0.40 | ES | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-or-es-5-bo | ES | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-or-nq-15-fade | NQ | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-gap-es-8 | ES | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-vwap-es-20-1.5 | ES | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-rc-es-20-0.25 | ES | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-cr-es-3 | ES | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-tod-es-15 | ES | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-pb-nq-20 | NQ | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| p2c-vx-es-20 | ES | False | not_tested_no_real_data | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## ES/NQ data

- discover_data usable (any root on the mount): `True`
- this batch stopped: `True` reason: `no_usable_real_market_data`
- missing roots for this batch: ES, NQ
- planted_detected: `None` null_detected: `None`
- needed if fail-closed: PIT NT8 1m continuous unadjusted CSVs at $LUMINA_RESEARCH_DATA_DIR/{ES,NQ}/1m/*.csv (UTF-8 header timestamp,open,high,low,close,volume; UTC ISO-8601 with offset). Hashes are recorded in phase5_p2_es_nq_holdout_seal.json at pin 2026-01-28T23:00:00Z when both tapes exist. Do not invent bars.

## Holdout

MES/MNQ seal 85e4588f reused, not rewritten. ES/NQ seal file is `phase5_p2_es_nq_holdout_seal.json` only when PIT tapes exist. Survivors would get one
holdout pass; none are promoted.
