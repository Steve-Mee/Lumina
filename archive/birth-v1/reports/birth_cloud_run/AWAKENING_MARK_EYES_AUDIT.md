# AWAKENING_MARK_EYES_AUDIT

## Gate 0
- origin/main SHA `7bcdaa079e60c92c03b256ff49d7f9a7f1534876`
- parent branch used `origin/main`
- OBSERVATION_DIM `43`
- parent sha match `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
- dead-family flags present (shape/t025/bounce if on disk)
- hooks default False : yes
- date: `2026-09-04T08:50:09.619206+00:00`

## Eyes
- MarkEyesState file:line `lumina_core/birth/awakening_mark_eyes_obs.py:32`
- concat_mark_eyes file:line `lumina_core/birth/awakening_mark_eyes_obs.py:116`
- wrapper obs shape file:line `lumina_core/birth/awakening_mark_eyes_env.py:39`

## Train
- init=scratch `scratch`
- timesteps actual / cap `10000` / `10000`
- child sha256 `53df2d78be7ff824b6bca14da8a1554fc6d52bdec2ce85f2b2564ffe35451e85`
- isolated workspace `True`

## Eval
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

## Flags
{
  "source": "awakening_mark_eyes",
  "obs_dim_global": 43,
  "obs_dim_eyes": 46,
  "timesteps": 10000,
  "train_seed": 20260901,
  "init_policy": "scratch",
  "parent_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
  "child_sha256": "53df2d78be7ff824b6bca14da8a1554fc6d52bdec2ce85f2b2564ffe35451e85",
  "actual_timesteps": 10000,
  "optimizer_steps": 90,
  "replay_ran": true,
  "learn_called": true,
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
  },
  "tag": "EYES_OK",
  "HOLE_MOVED_A": true,
  "HOLE_MOVED_B": true,
  "law": "SHADOW",
  "licensed_next_family": "AWAKENING_MARK_EYES",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "shape_default": false,
  "t_family_shadow_on": false,
  "overall": "GRIND_REGRESS_AWAKENING_OPEN MARK_EYES_WINDOW EYES_MEASURE"
}

## Honesty
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

## Protocol inspect
{
  "observation_dim_43": "lumina_core/rl/observation_builder.py:36",
  "mark_eyes_obs_dim_46": "lumina_core/birth/awakening_mark_eyes.py:37",
  "timesteps_10000": "lumina_core/birth/awakening_mark_eyes.py:39",
  "hold_norm_120": "lumina_core/birth/awakening_mark_eyes.py:40",
  "child_zip": "lumina_core/birth/awakening_mark_eyes.py:41",
  "init_refused_parent": "lumina_core/birth/awakening_mark_eyes.py:80",
  "on_step_no_wick": "lumina_core/birth/awakening_mark_eyes_obs.py:32",
  "concat_requires_43": "lumina_core/birth/awakening_mark_eyes_obs.py:124",
  "wrapper_obs_shape_46": "lumina_core/birth/awakening_mark_eyes_env.py:39",
  "path_exit_shadow_default": "lumina_core/birth/awakening_path_exit_k3.py:22",
  "path_shape_shadow_default": "lumina_core/birth/awakening_path_shape_k3_dead.py:57",
  "license_eyes_both": "lumina_core/birth/awakening_mark_eyes_flags.py:157",
  "evaluate_only_learn": "lumina_core/birth/awakening_grind.py:104",
  "parent_sha_const": "lumina_core/birth/awakening_path_exit_k3.py:30",
  "gitpython_pin": "requirements-core.txt:140",
  "codecov_patch_50": "codecov.yml:16",
  "forbidden_write_parent_zip": "lumina_core/birth/awakening_mark_eyes.py:80",
  "forbidden_write_path_early_jsonl": "lumina_core/birth/awakening_mark_eyes.py:112",
  "forbidden_write_path_exit_k3_jsonl": "lumina_core/birth/awakening_mark_eyes.py:119",
  "state_on_step": "lumina_core/birth/awakening_mark_eyes_obs.py:32",
  "concat_mark_eyes": "lumina_core/birth/awakening_mark_eyes_obs.py:116",
  "missing_sites": [],
  "gate0_complete": true
}

## T0 / T1 / T3
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
{
  "actual_timesteps": 10000,
  "n_updates": 90,
  "workspace_isolated": true,
  "forbidden_init_refused": true,
  "init_policy": "scratch"
}
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

