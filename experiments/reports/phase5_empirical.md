# Phase 5 empirical proof

- generated_at: `2026-10-28T20:32:00.029110+00:00`
- agent_id: `empirical_proof_agent`
- overall floor_passed: `True`
- gate_suite_passed: `True`
- independent continuity floor_passed: `True`
- short_horizon_passed (TTD<=15): `True`
- medium_horizon_passed (TTD<=45): `True`
- mutation_kill_rate: `0.825` passed: `True`
- holdout_seeds: `8675309, 424242, 135790, 246801, 112358, 132134, 178101, 192837, 204060, 777277`
- primary_normal_far (`healthy_laplace`, floor <= 0.05): `0.0`
- primary_high_vol_far (`healthy_regime_switch`, floor <= 0.10): `0.03333333333333333`
- stress `high_vol_mixture` FAR (not a floor): `0.6833333333333333`

## Per-regime FAR / detection / TTD

| slice | n | FAR | FAR floor | detection | TTD max | TTD floor | pass |
|---|---|---|---|---|---|---|---|
| healthy_laplace | 60 | 0.0000 | 0.05 | 0.0000 | n/a | n/a | PASS |
| abrupt_student | 60 | 0.0000 | n/a | 1.0000 | 8.0 | 15 | PASS |
| gradual_smooth | 60 | 0.0000 | n/a | 1.0000 | 14.0 | 15 | PASS |
| healthy_regime_switch | 60 | 0.0333 | 0.10 | 0.0000 | n/a | n/a | PASS |
| high_vol_mixture | 60 | 0.6833 | stress | 0.0000 | n/a | n/a | reported |
| regime_laplace | 60 | 0.0000 | n/a | 1.0000 | 11.0 | 15 | PASS |
| material_break | 60 | 0.0000 | n/a | 1.0000 | 5.0 | 15 | PASS |
| regime=normal | 295 | 0.0000 | 0.05 | 1.0000 | 14.0 | 15 | PASS |
| regime=high_vol | 65 | 0.0308 | 0.10 | 0.0000 | n/a | n/a | PASS |
| slow_gradual_30 | 60 | 0.0000 | n/a | 1.0000 | 21.0 | 45 | PASS |
| slow_gradual_45 | 60 | 0.0000 | n/a | 1.0000 | 26.0 | 45 | PASS |
| slow_gradual_60 | 60 | 0.0000 | n/a | 1.0000 | 30.0 | 45 | PASS |


## Phase 1 gate (independent synthetics)

| case | seed | expected | passed | n_oos | PBO | DSR | WFE | purge/embargo | reasons |
|---|---|---|---|---|---|---|---|---|---|
| overfit_ar1_random_search | 314159 | False | False | 9 | 0.6571 | 0.0622 | -0.4113 | True/True | pbo_hard_reject,dsr_below_threshold,wfe_below_threshold |
| noise_ar1 | 314170 | False | False | 9 | 0.3571 | 0.0033 | 1.9407 | True/True | dsr_below_threshold |
| healthy_student_t_drift | 314182 | True | True | 9 | 0.0571 | 1.0000 | 1.0883 | True/True |  |
| pipeline_evaluate_candidate | 314200 | True | True | 9 | 0.2143 | 1.0000 | 1.2588 | True/True |  |

## Short horizon (fast/material breaks, TTD <= 15)

### short / material / FAR kinds

- seeds: `10` signals: `420`
- detection_rate: `1.0000`
- false_alarm_rate: `0.2389`
- max_time_to_detect: `14.0`

| kind | n | detection_rate | false_alarm_rate | median TTD | p90 TTD | max TTD |
|---|---|---|---|---|---|---|
| healthy_laplace | 60 | 0.0000 | 0.0000 | n/a | n/a | n/a |
| abrupt_student | 60 | 1.0000 | 0.0000 | 6.0 | 7.0 | 8.0 |
| gradual_smooth | 60 | 1.0000 | 0.0000 | 12.0 | 13.0 | 14.0 |
| healthy_regime_switch | 60 | 0.0000 | 0.0333 | n/a | n/a | n/a |
| high_vol_mixture | 60 | 0.0000 | 0.6833 | n/a | n/a | n/a |
| regime_laplace | 60 | 1.0000 | 0.0000 | 7.0 | 8.0 | 11.0 |
| material_break | 60 | 1.0000 | 0.0000 | 4.0 | 5.0 | 5.0 |


## Medium horizon (slow 30/45/60-day decay, TTD <= 45, detection >= 0.85)

Two horizons, reported separately. Short/material breaks: detection >= 0.85 within 15 trading days. Slow 30/45/60-day ramps: detection >= 0.85 within 45 trading days (target 40). High-vol FAR hard cap 0.10, target 0.08; 0.12 is not a pass. Primary high-vol FAR is `healthy_regime_switch` (between-window regime switch). `high_vol_mixture` is a reported STRESS test and does not decide the floor.

### slow kinds

- seeds: `10` signals: `180`
- detection_rate: `1.0000`
- false_alarm_rate: `0.0000`
- max_time_to_detect: `30.0`

| kind | n | detection_rate | false_alarm_rate | median TTD | p90 TTD | max TTD |
|---|---|---|---|---|---|---|
| slow_gradual_30 | 60 | 1.0000 | 0.0000 | 18.0 | 20.0 | 21.0 |
| slow_gradual_45 | 60 | 1.0000 | 0.0000 | 22.0 | 24.0 | 26.0 |
| slow_gradual_60 | 60 | 1.0000 | 0.0000 | 25.0 | 28.0 | 30.0 |


## Mutation kill rate (latest nightly report)

- path: `experiments/reports/phase4_mutation.json`
- observed: `kill_rate=0.8250 n_mutants=320 n_non_equivalent=320 equivalent_frac=0.0000`
- required: `kill_rate>=0.8 n_mutants>=320 equivalent_frac<=0.1`
- passed: `True`
