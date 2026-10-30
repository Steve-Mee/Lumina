# ADR-0072: P2 final-cycle search-space lock (6 hypotheses)

**Status:** Proposed
**Date:** 2026-10-30
**Deciders:** Onderzoeksteam prereg 2026-10-30 09:13 (FINALE-CYCLUS) (forwarded
by Steve; not Steve's opinion) + LUMINA Engineering

Addendum to ADR-0071. Does not rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50,
the 7/8 null gate, holdout pin `2026-01-28T23:00:00Z`, or Risk Core. Does not
reset the hard-stop counter.

Binding input: `docs/research/ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md`
content sha256 `106af5b23d2eeb24454a2174e8c59ae24fb69e78c9729bb6e2accf3452aedade`.

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
4. **Missing data blocks the hypothesis.** NQ tape, VIX, macro calendar, and
   cash index are required where listed. Blocked ids stay on the list.
5. **Forbidden.** Trials, SIM/promotion, opening holdout, Risk Core edits,
   a 2nd cycle, extra variants, raising min-DSR, resetting the stop counter.

## Consequences

### Positive

- The new book can no longer sit in `awaiting_search_space_prereg`.
- Ambiguous bands cannot become a post-hoc grid.

### Negative

- RV-01/RV-02/LH-03/LH-04 cannot produce power counts until their data exists.
- Opening the book allows a later CLI cycle; that cycle is still not run here.

## Alternatives considered

1. Grid 1.5 and 2.0 NR7 targets — rejected: 09:13 plus STOPTELLING cap; pick one.
2. Run Validation Gate trials now — rejected: explicit "DO NOT run trials".
3. Drop blocked hypotheses from `n_hypotheses` — rejected: the lock is 6.

## Links

- Team prereg: `docs/research/ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md`
- Operational lock: `experiments/reports/phase5_p2_search_space_preregister_2026-10-30.md`
- Code: `lumina_research/cycles/final_cycle.py`
- Related: ADR-0071
