# Independent PR #63 audit (strict, zero-gap)

Do not merge. No orders. Floors were not loosened.

Audit seeds (never in Phase 4 tuning, PR #63 independent set, or HOLDOUT_SEEDS):
`90210, 48151623, 73939133, 104729, 611953, 1299709, 15485863, 32452843, 49979687, 67867967`

Campaign: `n_per_kind=6`, `n_days=70`, 10 seeds (same shape as official verify).

## Checklist

| # | Item | Verdict |
|---|---|---|
| 1 | Gaps / placeholders / untested paths closed with tests | PASS with closures |
| 2 | Attack tests: holdout lock, SimSafetyGate, no order/fabric from `lumina_research` | PASS after closures |
| 3 | High-vol skip of material drawdown vs DD-only decay >=1.5x | FAIL detection 0.00 (floor 0.85) |
| 4 | Overfitting: holdout seeds vs tuning; fresh never-seen seeds | PASS numbers; process flag |
| 5 | `high_vol_mixture` FAR ~0.68 / 0.73 | Explained; stress-only; not a realistic persistent regime |
| 6 | Fresh mutation >=300 on monitoring changes | FAIL kill 0.656 (floor 0.80) on 320 change-file mutants |
| 7 | 12 templates pre-registered before `discover_data` | PASS |

## Fresh-seed per-regime table

| slice | n | FAR | FAR floor | detection | TTD max | TTD floor | pass |
|---|---|---|---|---|---|---|---|
| healthy_laplace | 60 | 0.0000 | 0.05 | 0.0000 | n/a | n/a | PASS |
| abrupt_student | 60 | 0.0000 | n/a | 1.0000 | 8.0 | 15 | PASS |
| gradual_smooth | 60 | 0.0000 | n/a | 1.0000 | 14.0 | 15 | PASS |
| healthy_regime_switch | 60 | 0.0000 | 0.10 | 0.0000 | n/a | n/a | PASS |
| high_vol_mixture | 60 | 0.7333 | stress | 0.0000 | n/a | n/a | reported |
| regime_laplace | 60 | 0.0000 | n/a | 1.0000 | 10.0 | 15 | PASS |
| material_break | 60 | 0.0000 | n/a | 1.0000 | 5.0 | 15 | PASS |
| regime=normal | 286 | 0.0000 | 0.05 | 1.0000 | 14.0 | 15 | PASS |
| regime=high_vol | 74 | 0.0000 | 0.10 | 1.0000 | 10.0 | 15 | PASS |
| slow_gradual_30 | 60 | 0.0000 | n/a | 1.0000 | 20.0 | 45 | PASS |
| slow_gradual_45 | 60 | 0.0000 | n/a | 1.0000 | 25.0 | 45 | PASS |
| slow_gradual_60 | 60 | 0.0000 | n/a | 1.0000 | 30.0 | 45 | PASS |

Official HOLDOUT_SEEDS were introduced in the same commit as variance scaling, 3-window confirm, DD skip, and the primary-FAR redefinition (`c4127c4`). They were not a pre-registered holdout. They are disjoint from Phase 4 tuning. This never-seen seed set still meets the frozen FAR/TTD floors under the new primary definition.

## Item 3 — DD skip in high_vol

`assess_material` sets `dd_hit = False` whenever `vol_regime == "high_vol"`. Allowed mitigations were variance scaling and 3-window confirm only.

DD-only probe (rolling mean stays above OOS; path peak-to-trough 0.40 >= 1.5x OOS range 0.24):

- normal vol: material severity 1 (deweight)
- high vol (VIX=30): material severity 0; combined monitor stays active
- live monitor: 0 / 12 detected, max TTD n/a vs floors 0.85 / 15

Re-enabling DD (keeping vol_scale) on a 6-path `healthy_regime_switch` probe raised FAR to ~0.33 > 0.10. Not applied. Floors not loosened.

IC collapse in high vol still detects (control). The hole is DD-only, not a total high-vol blind spot.

## Item 5 — mixture FAR

Generator is iid 40% `N(μ, 1.60 σ_oos)` / 60% `N(μ, 0.70 σ_oos)` with constant mean and no VIX path. Official holdout FAR 0.6833; this audit 0.7333.

On 60 paths (holdout+audit seeds): 48 alarmed (FAR 0.80 on that probe); 47 of 48 alarms while the window still labeled **normal**. Ready windows: 2063 normal vs 997 high_vol. Intra-window heteroskedastic chop makes rolling-mean / CUSUM / IC-Sharpe twitch. It is not a quiet-then-loud between-window regime, so it is a harsh stress number, not a realistic persistent high-vol book. Primary FAR stays `healthy_regime_switch`.

## Item 6 — mutation

320 non-equivalent mutants on `material.py`, `horizons.py`, `vol_regime.py`, `acceptance.py`, `statistics.py`, `monitor.py`. Kill rate **0.656** (210 killed, 110 survived). Floor 0.80 not met. Not loosened. Kill battery was expanded; horizons compares on tie ranks remain mostly equivalent and material.py still has 50 survivors.

Packaged Phase 4 mix (committed `phase4_mutation.json`) remains 0.825 on the older file set.

## Fixes pushed

- Holdout timestamps must be strictly increasing; unknown `assert_not_holdout` purposes refuse.
- Attack tests: purpose tricks, loader paths (csv/jsonl/binary/env), SimSafetyGate, AST scan for live/order/fabric.
- Pre-register vs `discover_data` call-order test.
- DD-only high-vol floor test (fails until detection meets 0.85).
- Phase 5 mutant kill-battery coverage; `PHASE5_CHANGE_FILES` iterator.
