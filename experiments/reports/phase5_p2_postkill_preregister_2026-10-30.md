# P2 post-kill follow-up — pre-registration (2026-10-30)

**Committed before any new strategy-run.** Do not change these locks after
seeing bars. Optional plants are **not** in this file. No new large cycle.

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-POSTKILL-20261030T0638.md`
content sha256 `311ea60a1e8b3f832884669791d9e324c578822f3793db781cb54b9e79590c3b`
(prefix `311ea60a`).

Stacked draft PR #72. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched. ES CSV not in git.**

Does **not** rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50, the 7/8 null gate,
or the limited-es `p2l-*` kill. Fresh ids only.

## Diagnosis first (existing limited-es PIT; not extra trials)

Source: `experiments/reports/phase5_p2_limited_es.json` /
`phase5_p2_limited_es_results.md`. Same pre-holdout ES tape
(sha256 `6100588d…`, 818851 bars, last bar `2026-01-28T22:00:00Z`).
Reading those columns does **not** increment `TrialRegistry`.

### Breakout MFE/MAE + exit reasons

| config | n | stop | target | time_stop | session_end | stop % | target % | sess % | mean MFE ticks | mean MAE ticks | MFE−MAE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `p2l-rc-es` | 682 | 81 | 12 | 0 | 589 | 11.9 | 1.8 | 86.4 | 96.651 | 90.742 | 5.909 |
| `p2l-vx-es` | 732 | 124 | 17 | 0 | 591 | 16.9 | 2.3 | 80.7 | 102.649 | 98.456 | 4.193 |

Session-end dominates. The 1.8 ATR target almost never fills. Mean MFE ≈ mean
MAE (a few ticks of MFE edge, not a 2R excursion). Stretching the target to
2.2–2.5 ATR is therefore a **low-probability** rescue: farther targets will
hit even less often unless the right tail of MFE is fat. The team still
allowed max two extra trials. This lock is that test, not a search.

### Per-trade cost breakdown (USD, CostModel 1.2.0 totals / n_trades)

| config | n | comm $ | half-spread $ | slippage $ | impact $ | total $ | comm/t | spread/t | slip/t | impact/t | total/t | gross | net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `p2l-rc-es` | 682 | 3960.60 | 8625.00 | 19354.71 | 445.36 | 32385.67 | 5.81 | 12.65 | 28.38 | 0.65 | 47.49 | −0.109 | −0.432 |
| `p2l-vx-es` | 732 | 4253.34 | 9262.50 | 23798.03 | 537.84 | 37851.71 | 5.81 | 12.65 | 32.51 | 0.73 | 51.71 | −0.486 | −0.865 |

Round-trip commission ≈ $5.74 card; modeled ~$5.81/trade. Slippage is the
bulk. Both rows already beat gross BE (hitrate 0.509 / 0.489 vs 0.333) and
are still **net negative**. Costs, not a missing 1.8 target, are the kill.

### TOD (context for the one allowed follow-up; not a revival)

`p2l-tod-es`: 589 trades, hitrate 0.494 vs fade BE 0.545, **gross +0.100,
net −0.206**, +OOS 3/8, DSR 0.002, PBO 0.343. Session-end 473/589 (80.3%).
Never promote on gross.

## Locked follow-up (max 3 fresh strategy trials)

| field | lock |
|---|---|
| instruments | ES only; **NQ closed** |
| tape | attached pre-holdout ES, sha256 `6100588d2f3e519bd815b8f952dc15f01d434cc2a2b70e6453d0c3a7477bbca6` |
| holdout | pin `2026-01-28T23:00:00Z` sealed; refuse timestamps `>=` pin |
| geometry fade (TOD) | `1.0×ATR14 / 1.2×ATR14` (unchanged) |
| geometry breakout | target **2.4×ATR14** (one number in 2.2–2.5; not a grid), stop **0.9×ATR14** |
| holding | RTH session flatten, `time_stop_bars=2000` |
| n strategy configs | **3** (2 breakout + 1 TOD). No extra variants |
| ids | new `p2p-*` (fresh trial; do not reuse killed `p2l-*` / `p2a-*`) |
| floors | DSR ≥ 0.95, PBO 0.50, +OOS share ≥ 0.60, median OOS after costs > 0 |
| null / control | v2 `linear_magnitude`, 32 seeds `20261029+i`, fail at `n_edge ≥ 4/32`; positive control must still pass under fade 1.0/1.2 **and** breakout 1.8/0.9 (method gate, not the 2.4 stretch) |
| DSR N | continues from limited-es high-water **78**. Every new `TrialRegistry` record counts. Controls, if re-run, also count |
| promotion | none |
| SIM / REAL | none |
| plants | none (lower-hitrate / no-lookahead stay later) |

### Breakout stretch (exactly two)

| config_id | template | family | mode | lookback | threshold | target/stop | sibling killed |
|---|---|---|---|---|---|---|---|
| `p2p-rc-es` | `range_compression` | range_compression | breakout | 60 | 0.25 | **2.4 / 0.9** | `p2l-rc-es` 1.8/0.9 |
| `p2p-vx-es` | `volatility_expansion` | volatility_expansion | breakout | 60 | 0.75 | **2.4 / 0.9** | `p2l-vx-es` 1.8/0.9 |

Gross BE at 2.4/0.9 = `0.9/3.3` ≈ 0.273. If **both** are still net
negative after costs → **breakout family closed this cycle**. No third
breakout trial. No 2.2 vs 2.5 search.

### One refined TOD (pick: slightly longer horizon)

| config_id | template | family | mode | lookback | threshold | target/stop | session |
|---|---|---|---|---|---|---|---|
| `p2p-tod-es` | `time_of_day_inventory` | time_of_day | fade | **45** | 0.0 | 1.0 / 1.2 | `rth` |

**Why longer horizon, not a stricter RTH filter.** Allowed choice was one of
those two. `p2l-tod-es` is already `session_filter=rth` with RTH flatten;
entries are already first-hour inventory on RTH bars only (lowest turnover
of the six `p2l-*` rows). A new skip-open filter would be extra surface for
one trial. Catalog hold for this template is minutes 15–90 of cash; lookback
30 is the short end. Lookback **45** is a one-step move into that window,
same fade 1.0/1.2, same RTH flatten. Cost drag (gross+, net−) may get worse
if 45 adds trades; that is then a kill, not a reason to respec.

If this trial fails DSR or the +OOS-window gates → **TOD closed this cycle**.
Never promote on gross.

## Explicitly not in this lock

- No NQ row
- No `p2a-*` / `p2l-*` revival under those ids
- No optional plants
- No new large hypothesis cycle (longer-horizon / RTH-only / other families
  wait until this diagnosis + these three trials finish)
- No parameter changes after seeing results
- No holdout open, no SIM whitelist, no LIVE_RELEASE, no Risk Core edit

## Execution

`--cycle postkill-es --es-csv <attached pre-holdout ES>`. Fail-closed if the
CSV is missing or the sha256 is not `6100588d…`. Write a blocked report
rather than inventing bars.
