# ADR-0069: P2 team answers — null bar, midpoints, NQ lock

**Status:** Proposed
**Date:** 2026-10-29
**Deciders:** Onderzoeksteam answers 2026-10-29 17:34 and 18:17 (forwarded by Steve; not Steve's opinion) + LUMINA Engineering

Addendum to ADR-0067 / 0068. Does not rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50,
A2 planted detection, holdout pin `2026-01-28T23:00:00Z`, or Risk Core.

Binding input (17:34): `docs/research/ONDERZOEKERS-ANTWOORDEN-9VRAGEN-20261029T1734.md`
content sha256 `d792a116b8afb26ca2237122ea08edf31147416bd1bc309e2073ea811556c28c`.

Binding input (18:17, supersedes the 4/32-monitor clause):
`docs/research/ONDERZOEKERS-ANTWOORDEN-NULLGATE-20261029T1817.md`
content sha256 `8d6dc539bef53d4e4bfe6ec6cdaefdd5f06d2508c11407f9648bb293dfd547c2`.

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

1. **Null fail-closed (Q-NULL-1, 18:17).** Always report exact `n_a2/n_seeds`.
   A seed *hits A2* when median OOS > 0, +OOS ≥ 0.60, no structural decay.
   A seed *looks like an edge* for the gate when A2 fires **and** +OOS ≥ 0.875
   (7/8). Classify both counts with the same bar:
   - `≤ 3/32`: reliable
   - `≥ 4/32`: unreliable (**4 is fail**, not monitor). Band 4–5; 4 fails.
   Cycle stop uses `n_edge`, not raw `n_a2`. Target FPR 5–10% under the strict
   definition (`0–3/32` pass, `4/32` = 12.5% fail). Majority `16/32` is not
   the gate. No seed reroll. Frozen unclipped PIT `n_a2` stays diagnostic.
2. **Builder (Q-NULL-2 + 18:17 leak repair).** Keep detrend **and**
   sign-balance per walk-forward partition. Production builder is
   `linear_magnitude` (v2): linear OLS detrend, session-shuffle of residual
   signs, count-balance, greedy `|OC|` magnitude-balance. v1 `mean_shuffle`
   remains the before-score. ISO-week block of planted signs stays the
   report-only extra 8 seeds (Q-NULL-3), not the production shuffle.
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
10. **Research lock (18:17).** No strategy-run / template grid / NQ / holdout
    while the null leaks. CLI cycles `first`, `four-instrument`, `atr-es`
    require `experiments/reports/phase5_p2_null_only_validation.json` with
    `strict_gate_pass=true` and v2 `n_edge ≤ 3/32` on **both** ES and
    synthetic. Null-only validation (ES + synthetic) is the allowed repair
    run. Holdout timestamps `>= 2026-01-28T23:00:00Z` are asserted absent.

## Consequences

### Positive

- A leaky majority bar (5–10/32 A2 on unclipped D13) no longer "passes" as if
  it were calibrated. Exact A2 and exact 7/8 counts are both published.
- Reports stop publishing a >1 break-even that cannot be a win rate.

### Negative

- Unclipped A2 (MES 6/32, MNQ 10/32, ES 5/32, NQ 8/32) stays an A2-leak
  diagnostic above the 5–10% A2 target. Calibrated 7/8 (`n_edge`) is MES 0,
  MNQ 1, ES 0, NQ 0 — **reliable**, so the cycle stop does not fire.
- ATR ES 1/32 A2 stays reliable; ATR MES 4/32 A2 is now labeled **fail** on
  the diagnostic A2 count (18:17). Cycle stop still uses `n_edge`. ATR
  `n_edge` cannot be re-scored (PIT JSON has no per-seed +OOS). Template
  10/10 kill is unchanged (already DSR-dead).
- Midpoint positive-control PIT is still owed when CSVs are mounted.
- Null-only empirical (local ES pre-holdout, not committed; 818851 bars,
  `2023-10-01T22:01:00Z`–`2026-01-28T22:00:00Z`, 598 sessions):

  | tape | v1 A2 | v1 7/8 | v2 A2 | v2 7/8 |
  |---|---|---|---|---|
  | synthetic | 9/32 | 2/32 | 0/32 | 0/32 |
  | ES | 4/32 | 0/32 | 6/32 | 0/32 |

  Strict 7/8 goal met (`0/32` on both after v2). Raw ES A2 remains a
  diagnostic leak (6/32). JSON:
  `experiments/reports/phase5_p2_null_only_validation.json`.
  Strategy-run / templates / NQ / holdout were not executed in this repair.

## Alternatives considered

1. Keep majority 16/32 — rejected by the team.
2. Gate on raw A2 `≥4/32` — rejected: Type I ≈100% on 8 fair windows, contradicts
   "true null fails ≤5–10%".
3. Hard-fail at exactly 4/32 including MES ATR — **accepted at 18:17**
   (supersedes 17:34 monitor). 4 = fail on the strict 7/8 count.
4. Relax DSR so the four +OOS configs survive — rejected.
5. Run a lower-turnover grid now — rejected: must be a fresh pre-register.
6. Open NQ because unclipped NQ D13 planted — rejected: new pre-register
   required.
7. Replace session shuffle with ISO-week block-shuffle as the production
   mixer — rejected: that preserves intra-week drift and would raise FPR.
   Week-block stays report-only extra.
8. Run templates / strategy-run while FPR is unrepaired — rejected (18:17).

## Links

- Answers freeze (17:34): `docs/research/ONDERZOEKERS-ANTWOORDEN-9VRAGEN-20261029T1734.md`
- Answers freeze (18:17): `docs/research/ONDERZOEKERS-ANTWOORDEN-NULLGATE-20261029T1817.md`
- Pre-register: `experiments/reports/phase5_p2_null_v2_preregister_addendum_2026-10-29.md`
- Code: `lumina_research/cycles/null_model.py`, `null_only.py`, `null_lock.py`,
  `nq_lock.py`, `geometry.py`, `diagnostics.py`, `atr_cycle.py`
- Related: ADR-0067, ADR-0068
