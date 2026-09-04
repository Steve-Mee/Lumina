# AWAKENING_SELECT_OBJ_BOUNCE_AUDIT

## Gate 0
- origin/main SHA `53daabec73a6a303415c267e38203f77b6805f52`
- parent branch used `origin/main`
- T_LOCK / T_FP / EPS_SIT / MFE_LIFE unchanged : yes
- SHAPE flags tag if present `SHAPE_NONE`
- T025 flags tag if present `TRANSFER_FAIL`
- path_exit_k3 flags tag if present `HOLE_MOVED`
- PATH_EXIT_K3_SHADOW default False
- PATH_SHAPE_K3_SHADOW default False
- date: `2026-09-04T08:04:57.323538+00:00`

## Score
- bounce_r file:line `lumina_core/birth/awakening_select_obj_bounce.py:130`
- pred_bounce_weak file:line `lumina_core/birth/awakening_select_obj_bounce.py:138`
- BOUNCE_WEAK file:line `lumina_core/birth/awakening_select_obj_bounce.py:46`

## Source
- parent sha256 `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
- path_early A/B sha256 `4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb` / `0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356`
- path_exit_k3 (#27) A/B sha256 `0618dae7b58342898edbabdf3b2653cb36fc885c103b4715df17aa19f45435c9` / `00d8a5f446e16853c48000ef7c45352f896d9d580481baa3a4f3dd07f1afa3a9`
- path_exit_k3_t025 A/B sha256 `1d49b7d3b4b8ee718fd93f93481200076047ec4a60d145e4d9d35a149997a825` / `607aaa353e6f94f1846920b8df1c4a9af164b9ca7a3a8efc91a4665e0a43db06`
- path_shape_k3_dead A/B sha256 `` / ``

## Gate 1
{
  "A": {
    "n_U3": 117,
    "n_H3": 71,
    "n_W3": 37,
    "n_defined": 117,
    "missing_share": 0.0,
    "n_h_hit": 1,
    "n_w_hit": 1,
    "cov_H": 0.014084507042253521,
    "cov_W": 0.02702702702702703,
    "lift": -0.012942519984773507,
    "S_SPLIT": false,
    "S_HARM": false,
    "S_THIN": false,
    "S_MISSING": false,
    "bounce_p10_H": 1.473907972313739,
    "bounce_p50_H": 3.4535698916557602,
    "bounce_p90_H": 6.274417291005704,
    "bounce_p10_W": 1.3189796015052506,
    "bounce_p50_W": 3.6227621772331418,
    "bounce_p90_W": 7.585096088875443,
    "bounce_p10_U": 1.3728228497122383,
    "bounce_p50_U": 3.6085267549473197,
    "bounce_p90_U": 7.205819011189682,
    "min_bounce_U": 0.3764944017797075,
    "BOUNCE_WEAK": 0.5
  },
  "B": {
    "n_U3": 126,
    "n_H3": 79,
    "n_W3": 42,
    "n_defined": 126,
    "missing_share": 0.0,
    "n_h_hit": 0,
    "n_w_hit": 0,
    "cov_H": 0.0,
    "cov_W": 0.0,
    "lift": 0.0,
    "S_SPLIT": false,
    "S_HARM": false,
    "S_THIN": false,
    "S_MISSING": false,
    "bounce_p10_H": 1.8284909480858058,
    "bounce_p50_H": 3.778908717111029,
    "bounce_p90_H": 7.531204135989247,
    "bounce_p10_W": 2.149604985237638,
    "bounce_p50_W": 3.832323266402124,
    "bounce_p90_W": 5.930536660192605,
    "bounce_p10_U": 1.8291681112218756,
    "bounce_p50_U": 3.764718728312776,
    "bounce_p90_U": 6.817995449790042,
    "min_bounce_U": 0.802030850456357,
    "BOUNCE_WEAK": 0.5
  },
  "OBJ": {
    "tag": "OBJ_NONE",
    "law": "NONE",
    "licensed_next_family": "H_NONE",
    "gate1": "NONE",
    "S_SPLIT_A": false,
    "S_SPLIT_B": false,
    "S_HARM_A": false,
    "S_HARM_B": false
  }
}

## Gate 2
- replay_ran=false
- learn_called=false

## Flags
{
  "source": "path_early_measure",
  "BOUNCE_WEAK": 0.5,
  "EPS_SIT_HIST": 0.05,
  "MFE_LIFE_HIST": 0.25,
  "T_LOCK_HIST": -0.04787176712367987,
  "T_FP_HIST": -0.25,
  "replay_ran": false,
  "learn_called": false,
  "gate1_tag": "OBJ_NONE",
  "A_measure": {
    "n_U3": 117,
    "n_H3": 71,
    "n_W3": 37,
    "n_defined": 117,
    "missing_share": 0.0,
    "n_h_hit": 1,
    "n_w_hit": 1,
    "cov_H": 0.014084507042253521,
    "cov_W": 0.02702702702702703,
    "lift": -0.012942519984773507,
    "S_SPLIT": false,
    "S_HARM": false,
    "S_THIN": false,
    "S_MISSING": false,
    "bounce_p10_H": 1.473907972313739,
    "bounce_p50_H": 3.4535698916557602,
    "bounce_p90_H": 6.274417291005704,
    "bounce_p10_W": 1.3189796015052506,
    "bounce_p50_W": 3.6227621772331418,
    "bounce_p90_W": 7.585096088875443,
    "bounce_p10_U": 1.3728228497122383,
    "bounce_p50_U": 3.6085267549473197,
    "bounce_p90_U": 7.205819011189682,
    "min_bounce_U": 0.3764944017797075,
    "BOUNCE_WEAK": 0.5
  },
  "B_measure": {
    "n_U3": 126,
    "n_H3": 79,
    "n_W3": 42,
    "n_defined": 126,
    "missing_share": 0.0,
    "n_h_hit": 0,
    "n_w_hit": 0,
    "cov_H": 0.0,
    "cov_W": 0.0,
    "lift": 0.0,
    "S_SPLIT": false,
    "S_HARM": false,
    "S_THIN": false,
    "S_MISSING": false,
    "bounce_p10_H": 1.8284909480858058,
    "bounce_p50_H": 3.778908717111029,
    "bounce_p90_H": 7.531204135989247,
    "bounce_p10_W": 2.149604985237638,
    "bounce_p50_W": 3.832323266402124,
    "bounce_p90_W": 5.930536660192605,
    "bounce_p10_U": 1.8291681112218756,
    "bounce_p50_U": 3.764718728312776,
    "bounce_p90_U": 6.817995449790042,
    "min_bounce_U": 0.802030850456357,
    "BOUNCE_WEAK": 0.5
  },
  "tag": "OBJ_NONE",
  "S_SPLIT_A": false,
  "S_SPLIT_B": false,
  "law": "NONE",
  "licensed_next_family": "H_NONE",
  "gate1": "NONE",
  "optimizer_steps": 0,
  "evaluated_zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "shape_default": false,
  "t_family_shadow_on": false,
  "overall": "GRIND_REGRESS_AWAKENING_OPEN SELECT_OBJ_BOUNCE SHADOW_MEASURE"
}

## Honesty
#27 T_LOCK A HOLE_MOVED; B mean_r worse. Promoting T_LOCK is forbidden.
#28 T_FP=-0.25 TRANSFER_FAIL. k=3 R-threshold family exhausted as a controller.
#29 DEAD SHAPE_NONE. n_h_hit=0/0. EPS_SIT=0.05 not widened.
This ticket locks BOUNCE_WEAK=0.50 a priori (half-R recovery off paper MAE), not A/B-fitted.
No flatten. No learn(). Both path hooks stayed False.
Median not used as threshold.
Gate 1 tag=OBJ_NONE lift A/B=-0.012942519984773507/0.0
min_bounce U3 A/B=0.3764944017797075/0.802030850456357
Tag: OBJ_NONE. Law: NONE.
licensed_next_family: H_NONE.
Playground: no.
Evolution Proof stamped: False.
REAL: no.

## Protocol inspect
{
  "bounce_weak": "lumina_core/birth/awakening_select_obj_bounce.py:46",
  "eps_sit": "lumina_core/birth/awakening_path_shape_k3_dead.py:44",
  "mfe_life": "lumina_core/birth/awakening_path_shape_k3_dead.py:45",
  "t_lock": "lumina_core/birth/awakening_path_exit_k3.py:16",
  "t_fp": "lumina_core/birth/awakening_path_exit_k3_t025.py:1",
  "shape_shadow_default": "lumina_core/birth/awakening_path_shape_k3_dead.py:57",
  "t_shadow_default": "lumina_core/birth/awakening_path_exit_k3.py:22",
  "pred_no_t_tokens": "lumina_core/birth/awakening_select_obj_bounce.py:130",
  "license_obj_both": "lumina_core/birth/awakening_select_obj_bounce_flags.py:167",
  "law_always_none": "lumina_core/birth/awakening_select_obj_bounce_flags.py:173",
  "forbidden_write_path_early_jsonl": "lumina_core/birth/awakening_select_obj_bounce.py:96",
  "forbidden_write_path_exit_k3_jsonl": "lumina_core/birth/awakening_select_obj_bounce.py:101",
  "forbidden_write_path_exit_k3_t025_jsonl": "lumina_core/birth/awakening_select_obj_bounce.py:53",
  "forbidden_write_path_shape_jsonl": "lumina_core/birth/awakening_select_obj_bounce.py:111",
  "evaluate_only_learn": "lumina_core/birth/awakening_grind.py:104",
  "parent_sha_const": "lumina_core/birth/awakening_path_exit_k3.py:30",
  "gitpython_pin": "requirements-core.txt:140",
  "codecov_patch_50": "codecov.yml:16",
  "run_no_evaluate_only": "lumina_core/birth/awakening_select_obj_bounce_run.py:ok",
  "bounce_r": "lumina_core/birth/awakening_select_obj_bounce.py:130",
  "pred_bounce_weak": "lumina_core/birth/awakening_select_obj_bounce.py:138",
  "missing_sites": [],
  "gate0_complete": true
}

## Tm / T0 / T4
{
  "A": {
    "n_U3": 117,
    "n_H3": 71,
    "n_W3": 37,
    "n_defined": 117,
    "missing_share": 0.0,
    "n_h_hit": 1,
    "n_w_hit": 1,
    "cov_H": 0.014084507042253521,
    "cov_W": 0.02702702702702703,
    "lift": -0.012942519984773507,
    "S_SPLIT": false,
    "S_HARM": false,
    "S_THIN": false,
    "S_MISSING": false,
    "bounce_p10_H": 1.473907972313739,
    "bounce_p50_H": 3.4535698916557602,
    "bounce_p90_H": 6.274417291005704,
    "bounce_p10_W": 1.3189796015052506,
    "bounce_p50_W": 3.6227621772331418,
    "bounce_p90_W": 7.585096088875443,
    "bounce_p10_U": 1.3728228497122383,
    "bounce_p50_U": 3.6085267549473197,
    "bounce_p90_U": 7.205819011189682,
    "min_bounce_U": 0.3764944017797075,
    "BOUNCE_WEAK": 0.5
  },
  "B": {
    "n_U3": 126,
    "n_H3": 79,
    "n_W3": 42,
    "n_defined": 126,
    "missing_share": 0.0,
    "n_h_hit": 0,
    "n_w_hit": 0,
    "cov_H": 0.0,
    "cov_W": 0.0,
    "lift": 0.0,
    "S_SPLIT": false,
    "S_HARM": false,
    "S_THIN": false,
    "S_MISSING": false,
    "bounce_p10_H": 1.8284909480858058,
    "bounce_p50_H": 3.778908717111029,
    "bounce_p90_H": 7.531204135989247,
    "bounce_p10_W": 2.149604985237638,
    "bounce_p50_W": 3.832323266402124,
    "bounce_p90_W": 5.930536660192605,
    "bounce_p10_U": 1.8291681112218756,
    "bounce_p50_U": 3.764718728312776,
    "bounce_p90_U": 6.817995449790042,
    "min_bounce_U": 0.802030850456357,
    "BOUNCE_WEAK": 0.5
  },
  "BOUNCE_WEAK": 0.5
}
{
  "path_early_A_sha256": "4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb",
  "path_early_B_sha256": "0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356",
  "path_early_A_sha256_known": "4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb",
  "path_early_B_sha256_known": "0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356",
  "sha_match": true,
  "n_policy": 150,
  "n_policy_flags_A": null,
  "n_policy_flags_B": null,
  "optimizer_steps": 0,
  "hooks_false": true,
  "source": "awakening_select_obj_bounce",
  "BOUNCE_WEAK": 0.5,
  "replay_ran": false
}
{
  "path_early_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_early_A_close_ledger.jsonl",
    "n": 84,
    "mean_r": -1.037529935379773
  },
  "path_early_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_early_B_close_ledger.jsonl",
    "n": 88,
    "mean_r": -1.0515286004324211
  },
  "path_exit_k3_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_exit_k3_A_close_ledger.jsonl",
    "n": 46,
    "mean_r": -1.0377699206838897
  },
  "path_exit_k3_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_exit_k3_B_close_ledger.jsonl",
    "n": 49,
    "mean_r": -1.051534869069244
  },
  "path_exit_k3_t025_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_exit_k3_t025_A_close_ledger.jsonl",
    "n": 61,
    "mean_r": -1.0377593524524136
  },
  "path_exit_k3_t025_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/path_exit_k3_t025_B_close_ledger.jsonl",
    "n": 54,
    "mean_r": -1.0515558189164496
  },
  "path_shape_k3_dead_A": {
    "absent": true
  },
  "path_shape_k3_dead_B": {
    "absent": true
  }
}

## Forbidden-path grep
{
  "hygiene_token_in_birth": [],
  "model_learn_in_birth": [
    "lumina_core/birth/awakening_hole_tax_path.py",
    "lumina_core/birth/awakening_hole_tax_run.py",
    "lumina_core/birth/awakening_open_policy_signal_report.py",
    "lumina_core/birth/awakening_open_split_report.py",
    "lumina_core/birth/awakening_path_early_report.py",
    "lumina_core/birth/awakening_path_exit_k3_report.py",
    "lumina_core/birth/awakening_path_exit_k3_t025_report.py",
    "lumina_core/birth/awakening_path_shape_k3_dead_report.py",
    "lumina_core/birth/awakening_path_unreal_k3_report.py",
    "lumina_core/birth/awakening_select_obj_bounce_report.py",
    "lumina_core/birth/awakening_select_path.py",
    "lumina_core/birth/awakening_select_run.py"
  ],
  "playground": false
}

