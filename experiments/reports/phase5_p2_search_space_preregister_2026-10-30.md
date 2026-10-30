# P2 search-space pre-register — book `p2-next-search-space` (2026-10-30)

**Committed before any trial on this book.** This file opens the new DSR/PBO
book. It does **not** run the Validation Gate. DSR/PBO N stays **0**.

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md`
content sha256 `971bd2ef3ca798fdd0df976349420efd9915bf6f74734d5c1f6b50de51db743e`.

Data answers (09:36):
`docs/research/ONDERZOEKERS-ANTWOORDEN-DATA-20261030T0936.md`
content sha256 `e37cd59ead7db0779c2c8a61be0f59bce4a1e6b37281433480e9d6652741c8fb`.

Adding pre-holdout NQ / public VIX / public macro calendar is data
preparation inside this prereg. No new features or parameters.

Stacked draft PR #72. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched.** No trials in this
change.

Does **not** rewrite CostModel 1.2.0, DSR floor 0.95, PBO 0.50, or Risk Core.
Stop counter stays tripped (3 cycles / 19 prereg / 0 survivors) across books.

## Open conditions

| field | lock |
|---|---|
| book | `p2-next-search-space` |
| n_hypotheses | **6** (LH-02 and LH-04 dropped, still counted; cap 25; 1 cycle wins) |
| lower_turnover | true (hours, not 16-bar clips) |
| longer_horizon | true (90m–6h / EOD / weekend) |
| same_space_short_horizon | **false** |
| relative-value ideas | `p2s-rv-01`, `p2s-rv-02` (≥1 required) |
| NQ | NQOPEN only: relative-value ES vs NQ, pre-holdout, fresh ids |
| null | `linear_magnitude` |
| positive control | required (planted fade 1.0/1.2 **and** breakout 1.8/0.9). Not a 7th DSR trial. |
| kill (uniform) | **DSR ≥ 0.95 AND ≥7/8 OOS windows net-positive AND net > 0** |
| SIM / promotion | false |
| holdout | sealed |

## Ambiguous parameters — one value, no grid (09:36 approved)

| item | team band | locked value | why |
|---|---|---|---|
| LH-01 NR7 target | 1.5–2.0× NR7 range | **1.5×** | approved 09:36; prior 1.8–2.4 ATR targets filled ~2% after costs |
| RV-02 leg sizing | unspecified | **dollar-neutral** | approved 09:36; 1 ES vs NQ notional-matched (`50×ES / 20×NQ`), min 1 NQ |
| RV-01 z tails | wrote `z>2.5` | **\|z\| > 2.5** | ratio MR is two-sided; stop \|z\| ≥ 4.0; exit \|z\| < 0.5 |
| RV-02 gap sign | wrote `gap>0.4%` | **\|ES% − NQ%\| > 0.4** | fade the relative overnight gap |
| RV-01 VIX<25 | daily close | **previous day's close** | VIX close is 16:15 ET; same-day close is lookahead during RTH |

No other variant is pre-registered.

## Locked hypotheses (fresh ids). n_hypotheses stays 6.

| research | config_id | kind | status | instruments | entry | exit / stop | required data |
|---|---|---|---|---|---|---|---|
| RV-01 | `p2s-rv-01` | relative_value | testable | ES, NQ | RTH; ES/NQ 1m ratio \|z\| > 2.5 vs 20 prior session-close ratios; previous-day VIX < 25 | exit \|z\| < 0.5 or 6h; stop \|z\| ≥ 4.0 | ES, NQ, VIX |
| RV-02 | `p2s-rv-02` | relative_value | testable | ES, NQ | RTH open; \|ES% − NQ% overnight gap\| > 0.4%; fade, dollar-neutral | exit 50% fill or 90min; stop 1.5× relative gap | ES, NQ |
| LH-01 | `p2s-lh-01` | longer_horizon | testable | ES | RTH; previous day was NR7; first break of that day's H/L | target 1.5× NR7 range; stop opposite NR7 side; flatten EOD | ES |
| LH-02 | `p2s-lh-02` | longer_horizon | **dropped** (5 trades) | ES | Monday RTH open if Friday RTH \|OC\| > 1.5× ATR14 | exit 40% retrace or 2h; stop 1.0× Friday RTH range | ES |
| LH-03 | `p2s-lh-03` | longer_horizon | testable | ES | 5 minutes after CPI/NFP/FOMC if \|move from last pre-event close\| > 1.2× ATR14 | exit 50% retrace or 90min; stop 1.5× spike | ES, macro calendar |
| LH-04 | `p2s-lh-04` | longer_horizon | **dropped** (no free 1m SPX) | ES | cash–futures basis z > 2.0; fade to mean | exit z → 0; stop \|z\| ≥ 3.5 | ES, cash index |

Dropped ids stay on this list and in N. They are not replaced. They will not be trialled.

## Data pins (pre-holdout only)

| file | sha256 |
|---|---|
| ES_pre_holdout.csv | `6100588d2f3e519bd815b8f952dc15f01d434cc2a2b70e6453d0c3a7477bbca6` |
| NQ_pre_holdout.csv | `d60dd0c203ef31382def4278f4524a671bc7b4a050ab1334948ba693e269eed8` |
| NQ_pre_holdout.csv.gz | `4f5f7d4ef94e5dbecf3afea5021ad6d693eb7050ade439dd74d076d114e5c855` |
| VIX_daily_pre_holdout.csv | `481dc031c6d2b51b9150718c21c01b7f3706c99678ebf12b0edba19d0c8d2d1d` |
| macro_events_pre_holdout.csv | `104018d21552544a6c60ef52de0bbb6c82447c6afcb685e3059a14edd1c19aa7` |

Holdout: no row at or after `2026-01-28T23:00:00Z`. Cash index: none (LH-04 dropped).

## Not in this change

- No Validation Gate run
- No DSR/PBO N increment
- No 2nd cycle
- No search-space reuse of 1m short-horizon `p2l-*` / `p2p-*` / `p2a-*`
