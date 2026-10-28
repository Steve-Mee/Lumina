# Phase 5 empirical proof

- generated_at: `2026-10-28T19:16:40.733687+00:00`
- agent_id: `empirical_proof_agent`
- overall floor_passed: `False`
- gate_suite_passed: `True`
- independent continuity floor_passed: `False`
- short_horizon_passed (TTD<=15): `False`
- medium_horizon_passed (TTD<=45): `True`
- mutation_kill_rate: `0.825` passed: `True`

## Phase 1 gate (independent synthetics)

| case | seed | expected | passed | n_oos | PBO | DSR | WFE | purge/embargo | reasons |
|---|---|---|---|---|---|---|---|---|---|
| overfit_ar1_random_search | 314159 | False | False | 9 | 0.6571 | 0.1586 | -0.4113 | True/True | pbo_hard_reject,dsr_below_threshold,wfe_below_threshold |
| noise_ar1 | 314170 | False | False | 9 | 0.3571 | 0.0183 | 1.9407 | True/True | dsr_below_threshold |
| healthy_student_t_drift | 314182 | True | True | 9 | 0.0571 | 1.0000 | 1.0883 | True/True |  |
| pipeline_evaluate_candidate | 314200 | True | True | 9 | 0.2143 | 1.0000 | 1.2588 | True/True |  |

## Short horizon (fast/material breaks, TTD <= 15)

### short / material / FAR kinds

- seeds: `10` signals: `360`
- detection_rate: `1.0000`
- false_alarm_rate: `0.4750`
- max_time_to_detect: `13.0`

| kind | n | detection_rate | false_alarm_rate | median TTD | p90 TTD | max TTD |
|---|---|---|---|---|---|---|
| healthy_laplace | 60 | 0.0000 | 0.0000 | n/a | n/a | n/a |
| abrupt_student | 60 | 1.0000 | 0.0000 | 5.0 | 6.0 | 7.0 |
| gradual_smooth | 60 | 1.0000 | 0.0000 | 12.0 | 13.0 | 13.0 |
| high_vol_mixture | 60 | 0.0000 | 0.9500 | n/a | n/a | n/a |
| regime_laplace | 60 | 1.0000 | 0.0000 | 5.0 | 7.0 | 9.0 |
| material_break | 60 | 1.0000 | 0.0000 | 2.0 | 2.0 | 2.0 |


## Medium horizon (slow 30/45/60-day decay, TTD <= 45, detection >= 0.85)

Two horizons, reported separately. Short/material breaks: detection >= 0.85 within 15 trading days. Slow 30/45/60-day ramps: detection >= 0.85 within 45 trading days (target 40). High-vol FAR hard cap 0.10, target 0.08; 0.12 is not a pass.

### slow kinds

- seeds: `10` signals: `180`
- detection_rate: `1.0000`
- false_alarm_rate: `0.0000`
- max_time_to_detect: `31.0`

| kind | n | detection_rate | false_alarm_rate | median TTD | p90 TTD | max TTD |
|---|---|---|---|---|---|---|
| slow_gradual_30 | 60 | 1.0000 | 0.0000 | 18.0 | 19.0 | 20.0 |
| slow_gradual_45 | 60 | 1.0000 | 0.0000 | 21.0 | 23.0 | 26.0 |
| slow_gradual_60 | 60 | 1.0000 | 0.0000 | 24.0 | 27.0 | 31.0 |


## Mutation kill rate (latest nightly report)

- path: `/workspace/experiments/reports/phase4_mutation.json`
- observed: `kill_rate=0.8250 n_mutants=320 n_non_equivalent=320 equivalent_frac=0.0000`
- required: `kill_rate>=0.8 n_mutants>=320 equivalent_frac<=0.1`
- passed: `True`
