# AWAKENING_SLOPE_SCALE_VERDICT

**tag:** `SCALE_BODY`
**law:** `NONE`
**licensed_next_family:** `H_NONE`
**GENESIS_EYES_OK:** `False`
**in_band:** `True`
**world_ok:** `True`
**world_engineering_closed:** `True`
**drift_rth:** `8e-06`
**phase_blocks:** `6`
**seed_used:** `20260920`
**price_min:** `16124.75`
**price_max:** `25283.5`
**nq_min:** `12000.0`
**nq_max:** `28000.0`
**train_force_open:** `True`
**eval_force_open:** `False`
**slope_abs_used:** `0.004`
**prod_slope_abs:** `0.15`
**floor_waived:** `False`
**guard_bypassed:** `False`
**init_policy:** `scratch`
**learn_called:** `True`
**actual_timesteps:** `10000`
**REAL:** `no`
**G6_tag:** `REAL_DOOR_LOCKED`
**oracle_regime:** `False`
**fixture_train_hash:** `c9188a030e38e4bc`
**baseline_sha256:** `a9ffa8529e02f2d8`
**child_sha256:** `b83d2b67ef9d7937`
**MOVED_A:** `False`
**MOVED_B:** `True`

- attempts=[{'seed': 20260920, 'min': 16124.75, 'max': 25283.5, 'in_band': True}]
- Leg A n_policy base/child 150/150 n_H 0/0 mean_r -0.13990621213874965/-0.11045874813390434 Δmean_r 0.02944746400484531 HOLE_OK=True MOVED=False S_THIN=False S_HARM=False
- Leg B n_policy base/child 150/150 n_H 0/0 mean_r -0.2673944664305332/-0.10514684035807188 Δmean_r 0.16224762607246135 HOLE_OK=True MOVED=True S_THIN=False S_HARM=False

## Honesty

LAW: detector scaled with drift. 0.12*(8e-6/2.4e-4)=0.004. This is the last synthetic-world knob. This window refuses out-of-band seeds and does not disable the 1% guard. Production default unchanged. a9ffa852 is baseline, not clay. Scratch 46-dim V1. Floor 150 stays. GENESIS_EYES_OK stays false. SCALE_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture. License vs frozen a9ffa852 on THIS tape.

VERDICT is from disk flags, not memory.
