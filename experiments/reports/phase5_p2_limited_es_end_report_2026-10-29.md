# P2 limited ES strategy-run — end report (2026-10-29 23:07 GO)

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-LIMITEDGO-20261029T2307.md`
content sha256 `332003298fadfff06f28fced134d0a8c1a363933705d573cb3bd0407d4d9c414` (prefix `33200329`).

Stacked draft PR #72. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched. ES CSV not in git.**
Optional lower-hitrate / no-lookahead plants **not run**.

Pre-register: `phase5_p2_limited_es_preregister_2026-10-29.md`. Six configs including `p2l-tod-es`.
No extra variants. Parameters were not changed after seeing results.

- CostModel `1.2.0`, DSR floor `0.95`, PBO hard `0.5`
- fade `1.0/1.2`, breakout `1.8/0.9`, RTH flatten, `time_stop_bars=2000`
- Charter gate: WF 5–8 OOS, CPCV/static + bootstrap, DSR, PBO, costs, regimes
- Null: v2 `linear_magnitude`, 32 seeds, fail at `n_edge ≥ 4/32` (7/8)
- tape csv sha256 `6100588d…`, `818851` bars, `2023-10-01T22:01:00Z`–`2026-01-28T22:00:00Z`
- holdout_opened: `false`; nq_closed: `true`; promotion: `false`
- tested `6` killed `6` survivors `0`
- planted_detected: `True` null_detected: `False`
- control gate: fade 1.0/1.2 and breakout 1.8/0.9 both planted-detected, `passed_gate` true, null 7/8 `0/32`
- DSR `n_trials` is 73–78 (66 midpoint-control trials + hypothesis registration + the six configs). That is conservative deflation, not extra strategy variants. Max strategy configs remains 6.
- **overall_verdict: `all_kill_no_promotion`**

## Per-config gate

| config | trades | hitrate | BE | hit-BE | gross | net | +OOS | DSR | PBO | passed_gate | reject_reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `p2l-mr-es` | 734 | 0.484 | 0.545 | -0.062 | -0.352101 | -0.739593 | 1/8 | 0.000 | 0.343 | false | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| `p2l-or-fade-es` | 695 | 0.463 | 0.545 | -0.082 | -0.85704 | -1.1569 | 0/8 | 0.000 | 0.343 | false | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| `p2l-vwap-es` | 729 | 0.486 | 0.545 | -0.060 | -0.602953 | -0.9777 | 1/8 | 0.000 | 0.343 | false | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| `p2l-tod-es` | 589 | 0.494 | 0.545 | -0.051 | 0.0997857 | -0.206213 | 3/8 | 0.002 | 0.343 | false | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |
| `p2l-rc-es` | 682 | 0.509 | 0.333 | 0.175 | -0.108541 | -0.432397 | 1/8 | 0.000 | 0.343 | false | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| `p2l-vx-es` | 732 | 0.489 | 0.333 | 0.156 | -0.486223 | -0.86474 | 2/8 | 0.000 | 0.343 | false | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |

## Honest verdict

All six pre-registered configs fail the Validation Gate on this
pre-holdout ES tape. That is a kill, not a near-miss. PBO is 0.343
(below the 0.50 hard reject); the kills are DSR (all ≪ 0.95), negative
median OOS after costs, and +OOS share below 0.60. No window count is
above 3/8. Hitrate is below fade breakeven (0.545) on all four fade
rows; breakout hitrate is above 0.333 gross BE but still net-negative
after CostModel 1.2.0. Trade counts match the ATR ES siblings on the
same lookbacks and the same 818851-bar tape — a fresh `p2l-*` trial, not
a revival of killed `p2a-*` ids, and the same economic result.

No promotion, no SIM, no parameter search after seeing the numbers, no
extra variants.

## Hygiene

- No live / SIM orders
- Risk Core not modified
- NQ templates remain closed
- Holdout timestamps `>= 2026-01-28T23:00:00Z` were asserted absent
- Max trials = the six pre-registered configs (controls are gate, not variants)
- Optional diagnostics (lower-hitrate / no-lookahead plant) not run

