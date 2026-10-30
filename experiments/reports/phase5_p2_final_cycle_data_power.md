# P2 final-cycle data availability + power (2026-10-30 10:00)

Binding: `docs/research/ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md`
content sha256 `971bd2ef3ca798fdd0df976349420efd9915bf6f74734d5c1f6b50de51db743e`.

Data answers: `docs/research/ONDERZOEKERS-ANTWOORDEN-DATA-20261030T0936.md`
content sha256 `e37cd59ead7db0779c2c8a61be0f59bce4a1e6b37281433480e9d6652741c8fb`.

LH-03 answers: `docs/research/ONDERZOEKERS-ANTWOORDEN-LH03-20261030T1000.md`
content sha256 `0c549ee1a1ba901f1bc6620b2ace5b0c0b5e6736d869b863a33e10a931320c4f` (prefix `0c549ee1`).

Holdout pin `2026-01-28T23:00:00Z` unopened. No SIM/promotion. Risk Core untouched.
n_hypotheses stays **6**. Dropped LH-02 and LH-04 stay in N.

## Addendum (research team, NOT Steve)

- The 1.2× ATR14 threshold uses INTRADAY ATR(14) on 5-minute bars (SMA of the last 14 true ranges from bars whose close is strictly before the release, no lookahead), NOT daily ATR14. Clarification of the pre-registered parameter, not a change to the hypothesis.
- RV-02 power is 59 trades. The research team accepts the low-power risk and still runs the trial. This is not a parameter change.

## Locked single values (no grid)

- LH-01 NR7 target = **1.5×** NR7 range
- RV-02 sizing = **dollar-neutral**
- RV-01 z = **|z| > 2.5** both tails; exit |z| < 0.5; stop |z| ≥ 4.0
- RV-02 gap = **|ES% − NQ%| > 0.4** at RTH open
- RV-01 VIX<25 = **previous day's close**
- LH-03 ATR = **5-minute ATR(14) strictly before release** (clarification)

## Trade counts (pre-holdout power, entries only)

| research | config_id | status | n_trades |
|---|---|---|---|
| RV-01 | `p2s-rv-01` | ready | **309** |
| RV-02 | `p2s-rv-02` | ready | **59** (low-power risk accepted) |
| LH-01 | `p2s-lh-01` | ready | **102** |
| LH-02 | `p2s-lh-02` | dropped | **5** (reason) |
| LH-03 | `p2s-lh-03` | ready | **62** |
| LH-04 | `p2s-lh-04` | dropped | — (no free 1m SPX) |

LH-03 diagnostic (5-minute ATR14, no lookahead):
73 events; 73 have a +5min bar; 0 lack 14 five-minute true ranges before the release; **62** exceed 1.2× 5-minute ATR14.

Kill still: DSR ≥ 0.95 AND ≥7/8 OOS+ AND net > 0.

JSON: `phase5_p2_final_cycle_data_power.json`.
