# P2 post-kill follow-up — end report (2026-10-30 06:38)

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-POSTKILL-20261030T0638.md`
content sha256 `311ea60a1e8b3f832884669791d9e324c578822f3793db781cb54b9e79590c3b` (prefix `311ea60a`).

Stacked draft PR #72. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched. ES CSV not in git.**
Optional plants **not run**. No new large cycle.

Pre-register: `phase5_p2_postkill_preregister_2026-10-30.md` (commit `72078670`, content sha256 `d259b84e636358c304756ccebca7728b3ecdda1a5bc695fa90c757916c505cec`).
Three fresh `p2p-*` ids. Breakout target 2.4 ATR / stop 0.9. TOD lookback 45.
DSR N continues from limited-es high-water 78.

- CostModel `1.2.0`, DSR floor `0.95`, PBO hard `0.5`
- holdout_opened: `false`; nq_closed: `true`; promotion: `false`; plants: `false`
- **overall_verdict: `all_kill_no_promotion`**
- breakout family: `closed_net_negative`; TOD: `closed_failed_gates`

## Breakout diagnostics (limited-es PIT, not extra trials)

| config | n | stop | target | time_stop | session_end | stop % | tgt % | sess % | mean MFE | mean MAE | MFE−MAE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `p2l-rc-es` | 682 | 81 | 12 | 0 | 589 | 11.9% | 1.8% | 86.4% | 96.651 | 90.742 | 5.909 |
| `p2l-vx-es` | 732 | 124 | 17 | 0 | 591 | 16.9% | 2.3% | 80.7% | 102.649 | 98.456 | 4.193 |

| config | comm $ | half-spread $ | slippage $ | impact $ | total $ | comm/t | spread/t | slip/t | impact/t | total/t | gross | net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `p2l-rc-es` | 3960.60 | 8625.00 | 19354.71 | 445.36 | 32385.67 | 5.81 | 12.65 | 28.38 | 0.65 | 47.49 | -0.108541 | -0.432397 |
| `p2l-vx-es` | 4253.34 | 9262.50 | 23798.03 | 537.84 | 37851.71 | 5.81 | 12.65 | 32.51 | 0.73 | 51.71 | -0.486223 | -0.86474 |

Session-end is 80–86% of exits. The 1.8 ATR target fills on ~2% of trades.
Mean MFE ≈ mean MAE. Slippage dominates the four-leg bill (~$28–33/trade).
Both siblings already beat gross BE 0.333 and are still net negative.

## TOD pick (same geometry, longer horizon)

`p2l-tod-es` sibling: n=589, hitrate=0.494 vs BE 0.545, gross 0.0997857, net -0.206213, +OOS 3/8, DSR 0.002. Session-end 473/589 (80.3%). Never promote on gross. Locked follow-up is `p2p-tod-es` lookback 45 (catalog hold 15–90m; RTH already locked).

## New trials vs gates

| config | trades | hitrate | BE | gross | net | +OOS | DSR | PBO | n_trials | passed_gate | reject_reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `p2p-rc-es` | 676 | 0.510 | 0.273 | -0.0303585 | -0.35033 | 2/8 | 0.000 | 0.686 | 148 | false | pbo_hard_reject,dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| `p2p-vx-es` | 719 | 0.499 | 0.273 | 0.230361 | -0.129169 | 4/8 | 0.002 | 0.686 | 149 | false | pbo_hard_reject,dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| `p2p-tod-es` | 594 | 0.492 | 0.545 | 0.0383571 | -0.274804 | 3/8 | 0.000 | 0.686 | 150 | false | pbo_hard_reject,dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60,static_structural_decay |

tested `3` killed `3` survivors `0`
tape sha256 `6100588d…`, `818851` bars, `2023-10-01T22:01:00Z`–`2026-01-28T22:00:00Z`
control: Planted edge: at the first RTH bar of each session, the control knows the sign of that session's last-RTH-close minus first-RTH-open (unadjusted). It holds that direction until RTH close (session flatten, C10). Brackets are 1.8×ATR14 target / 0.9×ATR14 stop in index points (midpoint D13; not 16/8 and not the unclipped limit-move ceiling) so a shuffled 50% null is not a 2R artefact. time_stop_bars=2000 cannot fire inside one RTH session. Four-leg costs unchanged. Known size is the session RTH open-to-close move clipped at those ATR multiples minus costs. | fade 1/1.2: planted detected, passed_gate, null 7/8 0/32; breakout 1.8/0.9: planted detected, passed_gate, null 7/8 0/32

## Honest verdict

Breakout family: `closed_net_negative`. TOD: `closed_failed_gates`.
PBO 0.686 is above the 0.50 hard reject (CSCV on DSR N=148–150, which
includes the 78 limited-es seed plus midpoint controls). Independent of
PBO, every row fails DSR ≪ 0.95, median OOS after costs, and +OOS < 0.60.
`p2p-vx-es` and `p2p-tod-es` are gross-positive and net-negative — never
promote on gross. Stretching the breakout target to 2.4 ATR did not
rescue net PnL (target fills fell to 6 and 9). No promotion, no SIM,
holdout unopened.

## Hygiene

- No live / SIM orders
- Risk Core not modified
- NQ templates remain closed
- Holdout timestamps `>= 2026-01-28T23:00:00Z` stay unopened
- Max new strategy configs = 3 pre-registered `p2p-*`
- Optional plants not run
- No new large hypothesis cycle

