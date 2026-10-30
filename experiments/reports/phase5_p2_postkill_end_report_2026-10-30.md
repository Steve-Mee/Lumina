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
- **overall_verdict: `tape_missing_no_new_trials`**
- breakout family: `pending_tape`; TOD: `pending_tape`

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

No new `p2p-*` trials were executed. The attached pre-holdout ES tape is
not on this VM. Searched:

- `/tmp/lumina-es/ES_pre_holdout.csv`
- `$LUMINA_RESEARCH_DATA_DIR/ES/1m/*.csv`
- `data/research/ES/1m/*.csv`

Required: local CSV sha256 `6100588d2f3e519bd815b8f952dc15f01d434cc2a2b70e6453d0c3a7477bbca6`,
818851 bars, `2023-10-01T22:01:00Z`–`2026-01-28T22:00:00Z` (previous path
`/tmp/lumina-es/ES_pre_holdout.csv`). `$LUMINA_RESEARCH_DATA_DIR` unset.
Google Drive had no `ES_pre_holdout` / `ES_continuous_unadj` CSV.
Families stay `pending_tape` (not closed without a run). DSR N stays 78.

## Hygiene

- No live / SIM orders
- Risk Core not modified
- NQ templates remain closed
- Holdout timestamps `>= 2026-01-28T23:00:00Z` stay unopened
- Max new strategy configs = 3 pre-registered `p2p-*`
- Optional plants not run
- No new large hypothesis cycle

