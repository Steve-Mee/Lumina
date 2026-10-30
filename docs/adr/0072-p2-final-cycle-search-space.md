# ADR-0072: P2 final-cycle search-space lock (6 hypotheses)

**Status:** Proposed
**Date:** 2026-10-30
**Deciders:** Onderzoeksteam prereg 2026-10-30 09:13 (FINALE-CYCLUS) (forwarded
by Steve; not Steve's opinion) + LUMINA Engineering

Addendum to ADR-0071. Does not rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50,
the 7/8 null gate, holdout pin `2026-01-28T23:00:00Z`, or Risk Core. Does not
reset the hard-stop counter.

Binding input: `docs/research/ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md`
content sha256 `971bd2ef3ca798fdd0df976349420efd9915bf6f74734d5c1f6b50de51db743e`.

Data answers: `docs/research/ONDERZOEKERS-ANTWOORDEN-DATA-20261030T0936.md`
content sha256 `e37cd59ead7db0779c2c8a61be0f59bce4a1e6b37281433480e9d6652741c8fb`.

## Context

ADR-0071 capped `p2-next-search-space` at one cycle / 25 hypotheses and left
the book shut until an explicit search-space pre-register. The research team
then locked six hypotheses: two relative-value ES vs NQ ideas and four longer-
horizon ES ideas. This is the allowed fundamental change (lower turnover,
longer horizon, ≥1 relative-value idea). Docs/code plus a pre-holdout data-
availability and power (trade-count) check. **No trials.**

First principles: intellectual honesty (count power on pre-holdout bars;
block missing data instead of inventing tapes), fail-closed (one value per
ambiguous band; no grid), capital preservation (no SIM/promotion, holdout
sealed, Risk Core untouched).

## Decision

1. **Open the book** at N=0 with `n_hypotheses=6`, ids `p2s-rv-01`,
   `p2s-rv-02`, `p2s-lh-01`…`p2s-lh-04`. Null `linear_magnitude`. Positive
   control required, not counted as a 7th trial.
2. **Kill uniform:** DSR ≥ 0.95 AND ≥7/8 OOS windows net-positive AND net > 0.
3. **One value, no grid.** NR7 target **1.5×** range (not 2.0×). RV-02 sizing
   **dollar-neutral** (1 ES vs notional-matched NQ, min 1 NQ).
4. **Missing data blocks the hypothesis.** NQ tape, VIX, and macro calendar
   are required where listed. Blocked ids stay on the list.
5. **09:36 data prep.** Pre-holdout NQ, CBOE VIX, and BLS/Fed macro events
   are pinned. RV-01 VIX<25 uses the **previous day's close**. LH-02 and
   LH-04 are dropped and still count in `n_hypotheses=6`.
6. **Forbidden.** Trials, SIM/promotion, opening holdout, Risk Core edits,
   a 2nd cycle, extra variants, raising min-DSR, resetting the stop counter.

## Consequences

### Positive

- The new book can no longer sit in `awaiting_search_space_prereg`.
- Ambiguous bands cannot become a post-hoc grid.
- RV-01, RV-02, and LH-03 are unblocked for power (not for trials).

### Negative

- LH-02 (5 trades) and LH-04 (no free 1m SPX) stay in N but will not be trialled.
- Opening the book allows a later CLI cycle; that cycle is still not run here.

## Alternatives considered

1. Grid 1.5 and 2.0 NR7 targets — rejected: 09:13 plus STOPTELLING cap; pick one.
2. Run Validation Gate trials now — rejected: explicit "DO NOT run trials".
3. Drop blocked/dropped hypotheses from `n_hypotheses` — rejected: the lock is 6.

## 10:00 addendum (research team, NOT Steve)

Binding: `docs/research/ONDERZOEKERS-ANTWOORDEN-LH03-20261030T1000.md`
content sha256 `0c549ee1a1ba901f1bc6620b2ace5b0c0b5e6736d869b863a33e10a931320c4f`.

1. **LH-03 ATR clarification, not a hypothesis change.** The pre-registered
   1.2× ATR14 threshold is INTRADAY ATR(14) on 5-minute bars computed from
   bars strictly before the release (no lookahead). It is not daily ATR14.
   No other parameter changes. The hypothesis id stays `p2s-lh-03`.
2. **RV-02 limited power is accepted.** 59 trades. The team still runs the
   trial and records the low-power risk in the power report and the ledger.
3. **GO.** Run exactly RV-01, RV-02, LH-01, LH-03 (one cycle). Report the
   new LH-03 power first, then run all four. Dropped LH-02/LH-04 stay in
   `n_hypotheses=6`. 0 survivors → `research_line_stopped`.

## 10:00 GO result (research team, NOT Steve)

One cycle on book `p2-next-search-space`. Work dir was fresh
(`state/phase5-p2-next-search-space-v2`) so DSR N did not inherit a crashed
audit. Controls: planted detected, null 7/8 `0/32` on fade 1.0/1.2 and
breakout 1.8/0.9. n_tested=4, n_survivors=0, DSR/PBO N=74.

RV-02 executed 52 trades against the accepted 59-trade low-power lock.
LH-03 executed 59 trades on the 5-minute ATR(14) clarification (power 62).
All four fail DSR ≥ 0.95 and ≥7/8 OOS+. `research_line_stopped=true`.
No SIM/promotion. Holdout sealed. Risk Core untouched.

## Links

- Team prereg: `docs/research/ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md`
- Data answers: `docs/research/ONDERZOEKERS-ANTWOORDEN-DATA-20261030T0936.md`
- LH-03 answers: `docs/research/ONDERZOEKERS-ANTWOORDEN-LH03-20261030T1000.md`
- Operational lock: `experiments/reports/phase5_p2_search_space_preregister_2026-10-30.md`
- Code: `lumina_research/cycles/final_cycle.py`
- Related: ADR-0071
