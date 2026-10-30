# P2 final-cycle data availability + power (2026-10-30 09:36)

Binding: `docs/research/ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md`
content sha256 `971bd2ef3ca798fdd0df976349420efd9915bf6f74734d5c1f6b50de51db743e`.

Data answers: `docs/research/ONDERZOEKERS-ANTWOORDEN-DATA-20261030T0936.md`
content sha256 `e37cd59ead7db0779c2c8a61be0f59bce4a1e6b37281433480e9d6652741c8fb`.

**No trials.** DSR/PBO N stays 0. Holdout pin `2026-01-28T23:00:00Z` unopened.
No SIM/promotion. Risk Core untouched. n_hypotheses stays **6**.

## Data availability (pinned)

| source | present | sha256 prefix | range |
|---|---|---|---|
| ES pre-holdout | yes | `6100588d…` | 2023-10-01T22:01Z → 2026-01-28T22:00Z (818,851) |
| NQ pre-holdout | yes | `d60dd0c2…` | 2023-10-01T22:01Z → 2026-01-28T22:00Z (821,334) |
| VIX daily (CBOE) | yes | `481dc031…` | 1990-01-02 → 2026-01-28 (9,110) |
| macro CPI/NFP/FOMC | yes | `104018d2…` | 73 events (27/27/19) |
| cash index 1m SPX | **no** | — | LH-04 dropped |

No row at or after `2026-01-28T23:00:00Z`.

## Locked single values (09:36 approved; no grid)

- LH-01 NR7 target = **1.5×** NR7 range
- RV-02 sizing = **dollar-neutral**
- RV-01 z = **\|z\| > 2.5** both tails; exit \|z\| < 0.5; stop \|z\| ≥ 4.0
- RV-02 gap = **\|ES% − NQ%\| > 0.4** at RTH open
- RV-01 VIX<25 = **previous day's close** (VIX session close is 16:15 ET; same-day close is lookahead during RTH)

## Trade counts (pre-holdout power, entries only)

| research | config_id | status | n_trades |
|---|---|---|---|
| RV-01 | `p2s-rv-01` | ready | **309** |
| RV-02 | `p2s-rv-02` | ready | **59** |
| LH-01 | `p2s-lh-01` | ready | **102** |
| LH-02 | `p2s-lh-02` | **dropped** | 5 (reason) |
| LH-03 | `p2s-lh-03` | ready | **1** |
| LH-04 | `p2s-lh-04` | **dropped** | — (no free 1m SPX) |

LH-03: all 73 events have a +5min bar; 2 lack ATR lookback at the tape start; 70 five-minute spikes are ≤ 1.2× daily ATR14; **1** exceeds it (CPI 2024-04-10). The locked 1.2× daily ATR threshold is a high bar versus a 5-minute window. Not altered.

Kill still: DSR ≥ 0.95 AND ≥7/8 OOS+ AND net > 0. Not evaluated; no trial.

JSON: `phase5_p2_final_cycle_data_power.json`.
