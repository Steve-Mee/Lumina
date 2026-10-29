# ADR-0069: P2 team answers — null bar, midpoints, NQ lock

**Status:** Proposed
**Date:** 2026-10-29
**Deciders:** Onderzoeksteam answers 2026-10-29 17:34 (forwarded by Steve; not Steve's opinion) + LUMINA Engineering

Addendum to ADR-0067 / 0068. Does not rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50,
A2 planted detection, holdout pin `2026-01-28T23:00:00Z`, or Risk Core.

Binding input: `docs/research/ONDERZOEKERS-ANTWOORDEN-9VRAGEN-20261029T1734.md`
content sha256 `d792a116b8afb26ca2237122ea08edf31147416bd1bc309e2073ea811556c28c`.

## Context

PR #72 asked nine lock questions after the 16:03 advisory. The team answered.
The previous fail-closed null bar (`n_a2 ≤ 16/32`) was too loose: a method that
looks like an edge on 10 of 32 seeds still "passed". Using raw A2 at `≥4/32`
is too tight: with 8 OOS windows P(A2|fair)≈0.36 so P(n_a2≥4|32)≈1 and a true
null would always fail. The 1.634 BE column was a 1/1-tick placeholder. NQ
templates were only closed "this cycle".

First principles: extreme intellectual honesty (exact counts, A2 vs calibrated
edge split), fail-closed (DSR stays 0.95; four +OOS DSR-kills stay killed),
capital preservation (no orders, holdout sealed, Risk Core untouched).

## Decision

1. **Null fail-closed (Q-NULL-1).** Always report exact `n_a2/n_seeds`.
   A seed *hits A2* when median OOS > 0, +OOS ≥ 0.60, no structural decay.
   A seed *looks like an edge* for the gate when A2 fires **and** +OOS ≥ 0.875
   (7/8). Classify both counts with the same bar:
   - `≤ 3/32`: reliable
   - `4/32`: borderline, monitor (MES ATR A2). Gate may continue.
   - `≥ 5/32`: unreliable
   Cycle stop uses `n_edge`, not raw `n_a2`. P(n_edge≥4 | 32)≈0.025, inside a
   conservative 5–10% Type I band. Majority `16/32` is not the gate. No seed
   reroll. No PIT CSVs in this workspace, so existing seed counts are
   re-scored, not re-run.
2. **Builder (Q-NULL-2).** Keep detrend **and** sign-balance per walk-forward
   partition. Do not drop either.
3. **Week-block (Q-NULL-3).** ISO calendar-week shuffle, 8 seeds
   `20261129+i`. Extra reported check only. Never the gate. Month is too coarse.
4. **Midpoints (Q-GEO).** Fade `1.0/1.2` and breakout `1.8/0.9` are
   pre-registered midpoints, not final. The positive control must pass under
   exactly those params. Existing ATR D13 record is 1:1 `1.5×ATR14`. Midpoint
   D13 is coded (`execute_control(..., target_atr=, stop_atr=)`); synthetic
   tape must detect the plant. PIT midpoint D13 is not executed here (no CSVs).
5. **Flatten (Q-GEO).** Gap/opening flatten at last allowed bar of the relevant
   session (RTH when the filter is RTH) or a pre-registered time stop. Never
   UTC calendar midnight.
6. **Unbracket hitrate (Q-GEO).** Report horizons 16, 60, and 120 bars.
   Diagnostics, not extra TrialRegistry trials.
7. **DSR-only kills (Q-REPORT).** `p2a-or-bo-es`, `p2a-rm-es`, `p2a-pb-es`,
   `p2a-gap-es` stay killed. No promotion. DSR floor stays 0.95. A
   lower-turnover version is a **new pre-register** (fresh trial), not a rerun
   of this grid, and is not run in this change.
8. **Break-even (Q-REPORT-1).** Per-family gross BE = `stop_atr / (target_atr +
   stop_atr)`. No-bracket (gap) is `n/a`. Drop the 1/1-tick `1.634` artefact
   (win rate cannot exceed 1). Net cost-adjusted ATR BE needs a representative
   ATR from a PIT tape; not invented.
9. **NQ (Q-NQ-1).** NQ templates stay closed until a new pre-register is
   **explicitly approved**. A reliable unclipped null is not that approval.

## Consequences

### Positive

- A leaky majority bar (5–10/32 A2 on unclipped D13) no longer "passes" as if
  it were calibrated. Exact A2 and exact 7/8 counts are both published.
- Reports stop publishing a >1 break-even that cannot be a win rate.

### Negative

- Unclipped A2 (MES 6/32, MNQ 10/32, ES 5/32, NQ 8/32) stays an A2-leak
  diagnostic above the 5–10% A2 target. Calibrated 7/8 (`n_edge`) is MES 0,
  MNQ 1, ES 0, NQ 0 — **reliable**, so the cycle stop does not fire.
- ATR ES 1/32 A2 stays reliable; ATR MES 4/32 A2 is borderline. ATR `n_edge`
  cannot be re-scored (PIT JSON has no per-seed +OOS). Template 10/10 kill is
  unchanged (already DSR-dead).
- Midpoint positive-control PIT is still owed when CSVs are mounted.

## Alternatives considered

1. Keep majority 16/32 — rejected by the team.
2. Gate on raw A2 `≥4/32` — rejected: Type I ≈100% on 8 fair windows, contradicts
   "true null fails ≤5–10%".
3. Hard-fail at exactly 4/32 including MES ATR — rejected: team marked 4/32
   borderline/monitor.
4. Relax DSR so the four +OOS configs survive — rejected.
5. Run a lower-turnover grid now — rejected: must be a fresh pre-register.
6. Open NQ because unclipped NQ D13 planted — rejected: new pre-register
   required.

## Links

- Answers freeze: `docs/research/ONDERZOEKERS-ANTWOORDEN-9VRAGEN-20261029T1734.md`
- Code: `lumina_research/cycles/null_model.py`, `nq_lock.py`, `geometry.py`,
  `diagnostics.py`, `atr_cycle.py`
- Related: ADR-0067, ADR-0068
