# AWAKENING_MARK_EYES_VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN MARK_EYES_WINDOW EYES_MEASURE`
**Date:** 2026-09-04T08:50:09.619206+00:00
**Child sha256:** `53df2d78be7ff824b6bca14da8a1554fc6d52bdec2ce85f2b2564ffe35451e85`
**init_policy:** `scratch`
**actual_timesteps:** `10000`
**optimizer_steps:** `90`
**learn_called:** `true`
**Tag:** `EYES_OK`
**Law:** `SHADOW`
**Family:** `AWAKENING_MARK_EYES`
**licensed_next_family:** `AWAKENING_MARK_EYES`
**Evolution Proof stamped:** `False`
**Playground:** `no`
**REAL:** `no`

### T0 — identity
{
  "origin_main_sha": "7bcdaa079e60c92c03b256ff49d7f9a7f1534876",
  "OBSERVATION_DIM": 43,
  "MARK_EYES_OBS_DIM": 46,
  "parent_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
  "child_sha256": "53df2d78be7ff824b6bca14da8a1554fc6d52bdec2ce85f2b2564ffe35451e85",
  "init_policy": "scratch",
  "timesteps": 10000,
  "train_seed": 20260901,
  "ticks_sha16": "7e86c2bb1c71d514",
  "optimizer_steps": 90,
  "actual_timesteps": 10000,
  "child_zip": "awakening_mark_eyes_pi_star.zip",
  "source": "awakening_mark_eyes"
}

### T1 — train
{
  "actual_timesteps": 10000,
  "n_updates": 90,
  "workspace_isolated": true,
  "forbidden_init_refused": true,
  "init_policy": "scratch"
}

### T2 — eval vs path_early
{
  "A": {
    "n_policy": 150,
    "wr_policy": 0.5133333333333333,
    "mean_r_policy": 0.03702885329849976,
    "n_H": 23,
    "n_W": 49,
    "n_H_early": 78,
    "mean_r_early": -0.3092697822118258,
    "delta_n_H": 55,
    "delta_mean_r": 0.3462986355103256,
    "HOLE_MOVED": true,
    "S_MISSING": false,
    "S_MISSING_HOOK": false,
    "S_HARM": false,
    "S_THIN": false
  },
  "B": {
    "n_policy": 150,
    "wr_policy": 0.5733333333333334,
    "mean_r_policy": 0.1237743003390373,
    "n_H": 18,
    "n_W": 59,
    "n_H_early": 83,
    "mean_r_early": -0.17973357939421974,
    "delta_n_H": 65,
    "delta_mean_r": 0.30350787973325705,
    "HOLE_MOVED": true,
    "S_MISSING": false,
    "S_MISSING_HOOK": false,
    "S_HARM": false,
    "S_THIN": false
  }
}

### T3 — license
{
  "tag": "EYES_OK",
  "law": "SHADOW",
  "licensed_next_family": "AWAKENING_MARK_EYES",
  "family": "AWAKENING_MARK_EYES",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "shape_default": false,
  "overall": "GRIND_REGRESS_AWAKENING_OPEN MARK_EYES_WINDOW EYES_MEASURE"
}

### Honesty
Parent 8cc435c6 is the frozen Birth-exit baseline, not the init of this window.
#27 T_LOCK A HOLE_MOVED; B mean_r worse. Promoting T_LOCK is forbidden.
#28 T_FP=-0.25 TRANSFER_FAIL. k=3 R-threshold family exhausted.
#29 DEAD SHAPE_NONE. EPS_SIT=0.05 not widened.
#33 BOUNCE OBJ_NONE. BOUNCE_WEAK=0.50 not widened.
This window locks mark-path eyes a priori (unreal_r, close-to-close mae_r, bars_held_norm/120).
Paper high/low MAE is not an eye.
PPO.init = scratch. Parent weights not loaded.
One shot timesteps=10000 seed=20260901 actual=10000.
Tag: EYES_OK.
Law: SHADOW.
licensed_next_family: AWAKENING_MARK_EYES.
Playground: no.
Evolution Proof stamped: False.
REAL: no.

