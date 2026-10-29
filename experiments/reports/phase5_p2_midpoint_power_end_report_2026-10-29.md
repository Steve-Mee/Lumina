# Onderzoeksteam 21:29 — passed_gate fix + midpoint power on ES

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-MIDPOINT-20261029T2129.md`
content sha256 `af183d1d6a9f329942d84bf80854791d69b20cd4264a88ae3da1d9677116e757`
(prefix `af183d1d`).

Stacked draft PR #72 on #69. **No merge. No SIM/REAL orders. Holdout pin
`2026-01-28T23:00:00Z` unopened. Risk Core untouched. ES CSV not in git.**
Strategy-run (including limited) **not started**.

Pre-register committed **before** the run: git `a2a17799`,
`experiments/reports/phase5_p2_midpoint_power_preregister_2026-10-29.md`
content sha256 `785dbe86392873be12e5e43a80c9549a43c1b55640ed10bdbe974bc6fdcd5dcf`
(prefix `785dbe86`).

DSR **0.95**, PBO **0.50**, CostModel **1.2.0**, seeds `20261029+i`, v2
`linear_magnitude`, fade `1.0/1.2`, breakout `1.8/0.9` unchanged.

---

## 1. Cause of `planted_passed_gate=false`

Not a weak plant. Not a charter miss. **Control-wiring.**

`run_controls` evaluated the planted candidate first with 32 null dailies as
PBO peers. `evaluate_candidate` built a 33-config PBO matrix while
`TrialRegistry` still held one trial (the plant just recorded). `_judge`
correctly appended `trial_count_below_pbo_configs` and `doubt`. The 19:24
rows had DSR 1.0 and +OOS 100% and still failed that check.

Historical confirmation: `experiments/reports/phase5_p2_step4_control_respec.md`
already recorded planted `passed_gate=False` with the same reject pair.

The 32 nulls **are** trials. Planted DSR must be deflated for N=33.

**Fix:** evaluate the 32 nulls first (they increment the registry), then gate
the plant with those 32 series as PBO peers. After the fix: `pbo.n_configs=33`,
`n_trials=33`, `reject_reasons=[]`. The `trial_count_below_pbo_configs` check
in `gate.py` is unchanged. Tests that trip it were added, not weakened.

Reject reasons are now persisted on `ControlOutcome`.

## 2. Tape

Same bytes as 18:17/19:24 (csv sha256 `6100588d…`). 818851 bars,
`2023-10-01T22:01:00Z`–`2026-01-28T22:00:00Z`, 598 sessions. No timestamp
`>= 2026-01-28T23:00:00Z`.

## 3. Counts per magnitude and geometry

Drempel unchanged: median OOS > 0, +OOS ≥ 0.60, no decay, beats null.
Magnitude is a linear scale of the already-costed session net (same trades).

| mag | family | detected | passed_gate | median OOS | +OOS | DSR | PBO n | exact A2 | exact 7/8 | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.00 | fade 1.0/1.2 | yes | **yes** | 0.011601 | 1.000 | 1.000 | 33 | 4/32 | **0/32** | clean |
| 1.00 | breakout 1.8/0.9 | yes | **yes** | 0.011457 | 1.000 | 1.000 | 33 | 2/32 | **0/32** | clean |
| 0.50 | fade 1.0/1.2 | yes | **yes** | 0.005800 | 1.000 | 1.000 | 33 | 4/32 | **0/32** | clean |
| 0.50 | breakout 1.8/0.9 | yes | **yes** | 0.005729 | 1.000 | 1.000 | 33 | 2/32 | **0/32** | clean |
| 0.25 | fade 1.0/1.2 | yes | **yes** | 0.002900 | 1.000 | 1.000 | 33 | 4/32 | **0/32** | clean |
| 0.25 | breakout 1.8/0.9 | yes | **yes** | 0.002864 | 1.000 | 1.000 | 33 | 2/32 | **0/32** | clean |

100% median OOS matches the 19:24 JSON to all printed digits. 50% and 25%
are exact halves and quarters. Null `n_edge` stays 0/32 on every row (raw A2
signs are scale-invariant).

JSON: `experiments/reports/phase5_p2_midpoint_power.json`.

## 4. Power oordeel

**Not a power problem** at 50% or 25% of this known-size lookahead plant.
The drempel still fires; the packaged gate now passes; the null stays silent.

Caveat: 25% is still saturated (8/8 +OOS, DSR 1.0). This does **not** bound
the minimum detectable edge for a realistic strategy. It only shows that this
session-direction plant remains above the drempel at a quarter of current
size. A weaker plant is a later question.

The 7/8 gate was not loosened.

## 5. Limited strategy-run

**Not run.** Pre-register only:
`experiments/reports/phase5_p2_limited_es_preregister_2026-10-29.md`.
ES only, fade/mean-reversion + breakout/momentum, 6 configs, NQ closed, no
promotion, no SIM. Execution needs a new team OK.

## 6. Hygiene

- No live / SIM orders
- Risk Core not modified
- Tests not weakened (`trial_count_below_pbo_configs` still rejects; 4/32
  still fail; 7/8 unchanged)
- CSV not committed

## 7. Open vragen

1. 25% of this plant is still saturated. Does the team want a weaker plant
   (for example 12.5%, or a lower hit-rate plant) before a limited run?
2. Limited ES 6-config list is proposed, not executed. Confirm or trim before
   OK.
3. Fade raw A2 remains 4/32 under ATR midpoints (diagnostic). Same 19:24 rule:
   no A2-only repair.
