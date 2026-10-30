# P2 final-cycle strategy-run — end report (2026-10-30 10:00 GO)

Binding input (research team, **NOT** Steve):
`docs/research/ONDERZOEKERS-ANTWOORDEN-LH03-20261030T1000.md` sha256 `0c549ee1a1ba901f1bc6620b2ace5b0c0b5e6736d869b863a33e10a931320c4f` (prefix `0c549ee1`).

Stacked draft PR #72. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched.**

- The 1.2× ATR14 threshold uses INTRADAY ATR(14) on 5-minute bars (SMA of the last 14 true ranges from bars whose close is strictly before the release, no lookahead), NOT daily ATR14. Clarification of the pre-registered parameter, not a change to the hypothesis.
- RV-02 power is 59 trades. The research team accepts the low-power risk and still runs the trial. This is not a parameter change. Power count remains **59**.
- Runnable ids: `p2s-rv-01`, `p2s-rv-02`, `p2s-lh-01`, `p2s-lh-03`.
- Dropped inside n=6: `p2s-lh-02`, `p2s-lh-04` (not trialled).
- Kill: DSR≥0.95 AND ≥7/8 OOS+ AND net>0.
- CostModel `1.2.0`. Null `linear_magnitude`. Midpoint fade 1.0/1.2 and breakout 1.8/0.9.
- n_trials (this book) `74`. line_state `research_line_stopped`.
- control: planted=True null=False note=`Planted edge: at the first RTH bar of each session, the control knows the sign of that session's last-RTH-close minus first-RTH-open (unadjusted). It holds that direction until RTH close (session flatten, C10). Brackets are 1.8×ATR14 target / 0.9×ATR14 stop in index points (midpoint D13; not 16/8 and not the unclipped limit-move ceiling) so a shuffled 50% null is not a 2R artefact. time_stop_bars=2000 cannot fire inside one RTH session. Four-leg costs unchanged. Known size is the session RTH open-to-close move clipped at those ATR multiples minus costs. | fade 1/1.2: planted detected, passed_gate, null 7/8 0/32; breakout 1.8/0.9: planted detected, passed_gate, null 7/8 0/32`

| config | trades | gross/trade | net/trade | +OOS | DSR | PBO | verdict |
|---|---|---|---|---|---|---|---|
| `p2s-rv-01` | 286 | -0.0000 | -0.0006 | 2/8 | 0.0000 | 0.3571 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| `p2s-rv-02` | 52 | 0.0036 | 0.0000 | 4/8 | 0.0081 | 0.3571 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |
| `p2s-lh-01` | 90 | 0.0014 | 0.0009 | 4/8 | 0.0390 | 0.3571 | dsr_below_threshold,static_positive_share_below_60 |
| `p2s-lh-03` | 59 | -0.0007 | -0.0013 | 4/8 | 0.0000 | 0.3571 | dsr_below_threshold,negative_median_oos_after_costs,static_median_oos_not_positive,static_positive_share_below_60 |

Dropped (counted in n_hypotheses=6, not trialled): `p2s-lh-02` (5 trades), `p2s-lh-04` (no 1m SPX).

Survivors: **0**. `research_line_stopped=true`.
