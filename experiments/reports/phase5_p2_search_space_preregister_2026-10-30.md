# P2 search-space pre-register — book `p2-next-search-space` (2026-10-30)

**Committed before any trial on this book.** This file opens the new DSR/PBO
book. It does **not** run the Validation Gate. DSR/PBO N stays **0**.

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md`
content sha256 `106af5b23d2eeb24454a2174e8c59ae24fb69e78c9729bb6e2accf3452aedade`
(prefix `106af5b2`; prompt cited `971bd2ef` for the on-box freeze — this
committed file is the 09:13 text as added to the repo).

Stacked draft PR #72. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched.** No trials in this
change.

Does **not** rewrite CostModel 1.2.0, DSR floor 0.95, PBO 0.50, or Risk Core.
Stop counter stays tripped (3 cycles / 19 prereg / 0 survivors) across books.

## Open conditions

| field | lock |
|---|---|
| book | `p2-next-search-space` |
| n_hypotheses | **6** (absolute cap 25; 1 cycle wins) |
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

## Ambiguous parameters — one value, no grid

The 09:13 team file left two bands. This lock picks **one** each:

| item | team band | locked value | why |
|---|---|---|---|
| LH-01 NR7 target | 1.5–2.0× NR7 range | **1.5×** | prior 1.8–2.4 ATR targets filled on ~2% of ES trades after costs; nearer edge of the stated band |
| RV-02 leg sizing | unspecified | **dollar-neutral** | 1 ES vs NQ notional-matched at entry (`50×ES / 20×NQ`), minimum 1 NQ; one pair = one trade |

No other variant is pre-registered.

## Locked hypotheses (fresh ids)

| research | config_id | kind | instruments | entry | exit / stop | required data |
|---|---|---|---|---|---|---|
| RV-01 | `p2s-rv-01` | relative_value | ES, NQ | RTH; ES/NQ close-ratio z > 2.5 on 20 sessions; VIX < 25 | exit z < 0.5 or 6h; stop \|z\| ≥ 4.0 | ES, NQ, VIX |
| RV-02 | `p2s-rv-02` | relative_value | ES, NQ | RTH open; relative overnight gap (ES% − NQ%) > 0.4%; fade the spread, dollar-neutral | exit 50% fill or 90min; stop 1.5× relative gap | ES, NQ |
| LH-01 | `p2s-lh-01` | longer_horizon | ES | RTH; previous day was NR7; first break of that day's H/L | target 1.5× NR7 range; stop opposite NR7 side; flatten EOD | ES |
| LH-02 | `p2s-lh-02` | longer_horizon | ES | Monday RTH open if Friday RTH \|OC\| > 1.5× ATR14; fade Friday | exit 40% retrace or 2h; stop 1.0× Friday RTH range | ES |
| LH-03 | `p2s-lh-03` | longer_horizon | ES | 5 minutes after CPI/NFP/FOMC if \|move\| > 1.2× ATR14; fade the spike | exit 50% retrace or 90min; stop 1.5× spike | ES, macro calendar |
| LH-04 | `p2s-lh-04` | longer_horizon | ES | cash–futures basis z > 2.0; fade to mean | exit z → 0; stop \|z\| ≥ 3.5 | ES, cash index |

Blocked (missing data) hypotheses stay on this list. They are not replaced.

## Not in this change

- No Validation Gate run
- No DSR/PBO N increment
- No 2nd cycle
- No search-space reuse of 1m short-horizon `p2l-*` / `p2p-*` / `p2a-*`
