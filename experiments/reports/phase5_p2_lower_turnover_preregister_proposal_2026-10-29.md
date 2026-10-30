# Proposal only — lower-turnover fresh trial (NOT RUN)

Team 17:34 (Q-REPORT): the four ATR configs that are gross/net positive with
+OOS 0.625 and still fail DSR stay **killed**. DSR is not relaxed. A
lower-turnover version may only be proposed as a **new pre-register** (fresh
trial). This file is that proposal. It does **not** increment TrialRegistry.
It is **not** executed in this change. Holdout pin
`2026-01-28T23:00:00Z` stays closed. No SIM/REAL orders. NQ stays closed.
No new signal families (Phase 1 freeze).

## Why a fresh trial

Re-using `p2a-or-bo-es` / `p2a-rm-es` / `p2a-pb-es` / `p2a-gap-es` with a
tweaked lookback after seeing DSR-fail would be a respec of a killed grid.
The team forbade that. A later cycle may pre-register a **new** id set
before seeing bars.

## Locked if the team approves later (do not run now)

| field | proposed lock |
|---|---|
| instruments | ES only for the first fresh trial; MES = D13 control; **NQ closed** |
| geometry | same pre-registered midpoints: fade 1.0/1.2, breakout 1.8/0.9, gap = session flatten, no 1m bracket |
| holding | RTH session flatten or a pre-registered time stop **in hours**, not 16-bar clips |
| turnover | fewer entries: longer lookbacks, RTH-only, no `close_reversal` / `volume_imbalance` |
| n configs | max 8–12, named `p2b-*` (new ids) |
| floors | DSR ≥ 0.95, PBO 0.50, A2 unchanged |
| null | ADR-0069: exact A2 plus calibrated 7/8 `n_edge` (`≤3/32` reliable, `4/32` borderline, `≥5/32` fail-closed) |
| positive control | must pass under fade 1.0/1.2 **and** breakout 1.8/0.9 |

Do not fill a config table until the team explicitly approves this
pre-register. Do not copy the killed `p2a-*` ids.
