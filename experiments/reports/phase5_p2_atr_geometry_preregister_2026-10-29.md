# P2 per-family ATR/points geometry — pre-registration (2026-10-29)

Locked **before** the ES ATR rerun. Binding: onderzoeksteam advisory
`docs/research/ONDERZOEKERS-ANALYSE-4MARKTEN-20261029T1603.md` (sha `83476aa3`)
§2 and priority actions 2 and 5. Freeze commit `51872204`. Null audit
`phase5_p2_multiseed_null_preregister_2026-10-29.md` (`bf665e5d` + addendum).

Does **not** rewrite the 24-variant catalog, first-cycle 16/8, or holdout
seals. 16/8 is archived as a lab result, not as refuted economics.

## ATR (equal in points, micro vs mini)

| field | value |
|---|---|
| ATR | mean of the last **14 completed RTH sessions'** true range (RTH high − RTH low), **causal** (strictly prior sessions) |
| units | index **points**, not ticks |
| ES vs MES | same points for the same multiple (tick size 0.25 on both) |
| warmup | no entry while ATR is 0 (fewer than 1 completed prior RTH session) |

## Family geometry (midpoints of advisory ranges)

| class | families | target | stop | horizon |
|---|---|---|---|---|
| fade | mean_reversion, vwap_distance, time_of_day, opening_range fade | 1.0×ATR | 1.2×ATR | RTH flatten (`time_stop_bars=2000`) |
| breakout/momentum | opening_range breakout, regime_momentum, range_compression, volatility_expansion, trend_pullback | 1.8×ATR | 0.9×ATR | RTH flatten (`time_stop_bars=2000`) |
| gap/opening session | overnight_gap | **no 1m bracket** | **no 1m bracket** | session flatten only |

Stops fill on touch; targets on trade-through (unchanged). RTH-only.

## Positive control in this geometry

Same planted session-direction as ADR-0063, **1:1 1.5×ATR14** (inside the fade
stop range 1.0–1.5; 1:1 so the null is not a 2R artefact). Session flatten.
Drift-aware 32-seed null (ADR-0067). Known size = session OC clipped at 1.5×ATR.
Fail-closed: no respec if planted misses or the null is unreliable.

The unclipped 20000/20000 control remains the action-1 lab; this is the
geometry control for action 5.

## Action-5 grid (10 ES configs; MES = control only; NQ closed)

No new 1m high-turnover templates (`close_reversal`, `volume_imbalance` out).
Signals may still be 1m; **holding** is the RTH session, not a 16-bar clip.

| config_id | family | mode | lookback | threshold | target/stop |
|---|---|---|---|---|---|
| p2a-mr-es | mean_reversion | fade | 60 | 1.5 | 1.0 / 1.2 ATR |
| p2a-vwap-es | vwap_distance | fade | 60 | 1.5 | 1.0 / 1.2 ATR |
| p2a-tod-es | time_of_day | fade | 30 | 0.0 | 1.0 / 1.2 ATR |
| p2a-or-fade-es | opening_range | fade | 30 | 0.0 | 1.0 / 1.2 ATR |
| p2a-or-bo-es | opening_range | breakout | 30 | 0.0 | 1.8 / 0.9 ATR |
| p2a-rm-es | regime_momentum | follow | 120 | 0.40 | 1.8 / 0.9 ATR |
| p2a-rc-es | range_compression | breakout | 60 | 0.25 | 1.8 / 0.9 ATR |
| p2a-vx-es | volatility_expansion | breakout | 60 | 0.75 | 1.8 / 0.9 ATR |
| p2a-pb-es | trend_pullback | follow | 120 | 0.0 | 1.8 / 0.9 ATR |
| p2a-gap-es | overnight_gap | fade | 1 | 8 ticks (= 2.0 points) | none (session) |

Lookbacks and thresholds are catalog economics, not tuned on this tape. Gap
threshold is **2.0 points** (8 ticks at 0.25) so micro and mini match in points.

## Diagnostics (not extra trials)

Exit-reason counts; MFE/MAE ticks; hitrate with brackets off and exit at
`N=60` bars; hitrate under symmetric 1R/1R using the family's **stop** as R.
Gross/net in USD, ticks, and points. These do not increment `TrialRegistry`.

## Gaps (action 3, locked from a four-tape count)

| window | ES | NQ | MES | MNQ | action |
|---|---|---|---|---|---|
| 2025-07-13/14/15 | missing / missing / 671 | 119 / 1380 / 1380 | 119 / 1379 / 1380 | 0 / 0 / 668 | **ES-only** exclude 13–15; **MNQ** already excludes 14–15, add 13; do **not** drop NQ/MES |
| 2025-11-28 | 444 | 450 | 451 | 451 | already `KNOWN_GAPS` `*` |
| 2026-04-22..27, 2026-05-08/11/12 | ES holes | present | present | present | **holdout**; pin closed; do not evaluate; no MES fill |

## Floors / hygiene

DSR 0.95, PBO 0.50, A2 unchanged. CostModel 1.2.0. Holdout pin closed.
No SIM orders. Residual ETH-slippage: RTH and ETH coefficients are both 0.10
by documentation, not SIM-fit.

## Open questions

- Q-GEO-1: 1.0/1.2 and 1.8/0.9 are range midpoints; confirm vs other values in the bands.
- Q-GEO-2: session flatten vs calendar-day flatten for gap/OR.
- Q-GEO-3: unbracketed N=60 (1h) vs another fixed N.
