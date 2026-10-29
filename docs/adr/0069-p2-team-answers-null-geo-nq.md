# ADR-0069: P2 team answers — null bar, midpoints, NQ lock

**Status:** Proposed
**Date:** 2026-10-29
**Deciders:** Onderzoeksteam answers 2026-10-29 17:34, 18:17, 19:24, 21:29, 22:08, and 23:07 (forwarded by Steve; not Steve's opinion) + LUMINA Engineering

Addendum to ADR-0067 / 0068. Does not rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50,
A2 planted detection, holdout pin `2026-01-28T23:00:00Z`, or Risk Core.

Binding input (17:34): `docs/research/ONDERZOEKERS-ANTWOORDEN-9VRAGEN-20261029T1734.md`
content sha256 `d792a116b8afb26ca2237122ea08edf31147416bd1bc309e2073ea811556c28c`.

Binding input (18:17, supersedes the 4/32-monitor clause):
`docs/research/ONDERZOEKERS-ANTWOORDEN-NULLGATE-20261029T1817.md`
content sha256 `8d6dc539bef53d4e4bfe6ec6cdaefdd5f06d2508c11407f9648bb293dfd547c2`.

Binding input (19:24, null-only follow-up):
`docs/research/ONDERZOEKERS-ANTWOORDEN-NULLVAL-20261029T1924.md`
content sha256 `74e5941cc57fccaa5d08ea32bcf86bbc07b310db6efdabda431071bb4b9e777c`.

Binding input (21:29, passed_gate + power):
`docs/research/ONDERZOEKERS-ANTWOORDEN-MIDPOINT-20261029T2129.md`
content sha256 `af183d1d6a9f329942d84bf80854791d69b20cd4264a88ae3da1d9677116e757`.

Binding input (22:08, power floor + limited prereg; research-team answers, not Steve):
`docs/research/ONDERZOEKERS-ANTWOORDEN-POWER-S4-20261029T2208.md`
content sha256 `991138fdd4b741041e3288387dd8aaf89a09652329ada7eec7eaa0f037bfae9d`.

Binding input (23:07, GO for the limited ES run; research-team answers, not Steve):
`docs/research/ONDERZOEKERS-ANTWOORDEN-LIMITEDGO-20261029T2307.md`
content sha256 `332003298fadfff06f28fced134d0a8c1a363933705d573cb3bd0407d4d9c414`.

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
4. **Midpoints (Q-GEO + 19:24).** Fade `1.0/1.2` and breakout `1.8/0.9` are
   pre-registered midpoints, not final. The positive control must pass under
   exactly those params. Existing ATR D13 record is 1:1 `1.5×ATR14`. PIT
   midpoint D13 is the allowed next run (ES tape, holdout cut, no templates).
   Pre-register `phase5_p2_midpoint_d13_preregister_2026-10-29.md` before that
   run: known size, detection drempel, 32 seeds.
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
11. **Null-only follow-up (19:24).** No separate raw-A2 repair; strict
    `n_edge` 0/32 is enough; A2 stays diagnostic. 0/32 below the 5% floor is
    accepted with a power caveat; do **not** loosen the 7/8 gate. Next
    allowed run is midpoint D13 only. If the null stays `≤3/32` and the
    planted edge is not detected: power problem, stop. A limited
    strategy-run needs a new team OK after a clean detect + silent null.
12. **Passed-gate wiring (21:29).** `planted_passed_gate=false` on the 19:24
    DSR-1.0 / 100% +OOS plant was `trial_count_below_pbo_configs`: the plant
    was gated with 32 null PBO peers while `TrialRegistry` still held one
    trial. The 32 nulls **are** trials. Fix: evaluate nulls first so planted
    DSR/PBO see N=33. Do **not** remove the gate check. Then rerun the plant
    at 50% and 25% of known size (linear scale of costed session net; same
    midpoints and seeds). Limited strategy-run stays unrun until a new OK.
13. **Detection floor (22:08).** Before any limited strategy-run, rerun the
    same midpoint plant at 12.5% and 6.25% of known size. Same geometry,
    seeds, v2 builder, and null-first `passed_gate` wiring. Report +OOS /8,
    DSR, `passed_gate`, and strict null `/32`. A miss with a silent null is
    a power finding, not a looser gate. Limited ES grid: keep the six
    `p2l-*` configs unless `p2l-tod-es` is high turnover / ETH on existing
    data; no extra variants. This change records TOD **keep** (lowest
    n_trades of the six ATR siblings; RTH-only) and does **not** start the
    limited run.
16. **Limited ES GO (23:07).** Power at 6.25% is sufficient; the detection
    floor was not found but is not a reason to wait. Run exactly the six
    pre-registered `p2l-*` configs including `p2l-tod-es` on the attached
    pre-holdout ES tape. ES only. No NQ, no promotion, no SIM, holdout
    sealed, max trials = 6, no extra variants, no parameter changes after
    seeing results. Full Charter gate plus the 7/8 null gate. Optional
    lower-hitrate / no-lookahead plants stay later diagnostics, not this
    run.

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
- Midpoint D13 PIT (19:24, ES only, holdout cut): fade 1.0/1.2 and breakout
  1.8/0.9 both **detect** the planted edge (median OOS 0.0116 / 0.0115, +OOS
  8/8, DSR 1.0, beats null). Strict null `n_edge` **0/32** on both. Verdict
  `clean` (not a power miss). The 19:24 packaged gate `passed_gate` was
  false on the plant because of control wiring (`trial_count_below_pbo_configs`),
  not a weak edge. JSON: `experiments/reports/phase5_p2_midpoint_d13.json`.
- Midpoint power PIT (21:29, same ES tape, holdout cut): after the wiring
  fix, fade and breakout `passed_gate` is **true** at 100%, 50%, and 25%
  magnitude (PBO n_configs=33, n_trials=33, reject_reasons empty). Detection
  and `n_edge` 0/32 hold on all six rows. Median OOS scales linearly
  (0.0116 / 0.00580 / 0.00290 fade). Verdict `clean` at every band. No
  strategy-run. JSON: `experiments/reports/phase5_p2_midpoint_power.json`.
- Midpoint power floor PIT (22:08, same ES tape, holdout cut): fade and
  breakout stay `clean` at 12.5% and 6.25% (`passed_gate` true, +OOS 8/8,
  DSR 1.0, PBO n=33, `n_edge` 0/32). Median OOS is the exact eighth and
  sixteenth of the 19:24 known size. Detection floor of this lookahead
  plant is **at or below 6.25%**. Still saturated; not a realistic-strategy
  floor. JSON:
  `experiments/reports/phase5_p2_midpoint_power_floor.json`.
- Limited ES PIT (23:07 GO, same pre-holdout ES tape, holdout cut): six
  `p2l-*` configs including `p2l-tod-es`. Midpoint controls both pass
  (`passed_gate` true, null 7/8 `0/32`). All six templates **killed**
  (DSR ≪ 0.95, negative median OOS, +OOS ≤ 3/8). PBO 0.343 (not the
  kill). Kill rate 6/6. No promotion, no SIM, holdout unopened. JSON:
  `experiments/reports/phase5_p2_limited_es_end.json`.
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
9. Separate raw-A2 repair after v2 7/8 is 0/32 — rejected (19:24).
10. Loosen the 7/8 gate because FPR is 0/32 — rejected (19:24); power caveat
    instead. Limited strategy-run now — rejected until a new OK.
11. Drop `trial_count_below_pbo_configs` because the plant is a known edge —
    rejected (21:29). The check is correct; the control must register PBO
    peers as trials first.
12. Run the limited ES fade/breakout grid in this change — rejected (21:29);
    pre-register only.
13. Skip 12.5%/6.25% because 25% was already saturated — rejected (22:08);
    measure the floor.
14. Drop `p2l-tod-es` without checking existing ATR turnover/ETH — rejected.
    Existing PIT: lowest n_trades of the six, RTH-only. Keep 6 configs.
15. Start the limited ES run in this change after the floor check — rejected
    by the 22:08 task; preregister only. **Superseded at 23:07:** the
    research team GO runs the six locked configs on the attached ES tape
    with no promotion and no extra variants.
16. Drop `p2l-tod-es` at GO time — rejected; 23:07 keeps all six.
17. Open NQ, promote, or start SIM because the limited run exists —
    rejected.
18. Change lookbacks/thresholds/geometry after seeing limited-run numbers —
    rejected.
19. Run optional lower-hitrate / no-lookahead plants in this change —
    rejected (non-blocking, later).

## Links

- Answers freeze (17:34): `docs/research/ONDERZOEKERS-ANTWOORDEN-9VRAGEN-20261029T1734.md`
- Answers freeze (18:17): `docs/research/ONDERZOEKERS-ANTWOORDEN-NULLGATE-20261029T1817.md`
- Answers freeze (19:24): `docs/research/ONDERZOEKERS-ANTWOORDEN-NULLVAL-20261029T1924.md`
- Answers freeze (21:29): `docs/research/ONDERZOEKERS-ANTWOORDEN-MIDPOINT-20261029T2129.md`
- Answers freeze (22:08): `docs/research/ONDERZOEKERS-ANTWOORDEN-POWER-S4-20261029T2208.md`
- Answers freeze (23:07): `docs/research/ONDERZOEKERS-ANTWOORDEN-LIMITEDGO-20261029T2307.md`
- Pre-register (null v2): `experiments/reports/phase5_p2_null_v2_preregister_addendum_2026-10-29.md`
- Pre-register (midpoint D13): `experiments/reports/phase5_p2_midpoint_d13_preregister_2026-10-29.md`
- Pre-register (midpoint power): `experiments/reports/phase5_p2_midpoint_power_preregister_2026-10-29.md`
- Pre-register (midpoint power floor): `experiments/reports/phase5_p2_midpoint_power_floor_preregister_2026-10-29.md`
- Pre-register (limited ES): `experiments/reports/phase5_p2_limited_es_preregister_2026-10-29.md`
- PIT (limited ES): `experiments/reports/phase5_p2_limited_es_end.json`,
  `phase5_p2_limited_es_end_report_2026-10-29.md`
- Code: `lumina_research/cycles/null_model.py`, `null_only.py`, `null_lock.py`,
  `nq_lock.py`, `geometry.py`, `diagnostics.py`, `atr_cycle.py`,
  `positive_control.py`, `midpoint_d13.py`, `limited_es.py`, `runner.py`
- Related: ADR-0067, ADR-0068
