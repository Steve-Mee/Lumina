# AWAKENING_PATH_SHAPE_K3_DEAD_AUDIT

## Gate 0
- origin/main SHA `eb3184db8a7931991752e0e3eef3f1149269d20f`
- parent branch used `origin/cursor/awakening-path-exit-k3-t025-821a`
- T_LOCK still -0.04787176712367987 : yes
- T025 flags tag if present `TRANSFER_FAIL`
- PATH_EXIT_K3_SHADOW default False : yes
- PATH_SHAPE_K3_SHADOW default False : yes
- parent_loaded: `True`
- date: `2026-09-04T06:30:35.056964+00:00`

## Hook
- should_path_shape_k3_dead file:line `lumina_core/birth/awakening_path_shape_k3_dead.py:122`
- peek excursion file:line `lumina_core/birth/awakening_path_shape_k3_dead_peek.py:10`
- after_open_telem file:line `lumina_core/birth/awakening_path_exit_k3_hook.py:69`
- flatten site file:line `lumina_core/birth/sim_runner.py:force_flatten_this_step`
- mutual exclusion file:line `lumina_core/birth/awakening_path_exit_k3_hook.py:81`

## Source
- parent sha256 `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
- path_early A/B sha256 `4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb` / `0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356`
- path_exit_k3 (#27) A/B sha256 `0618dae7b58342898edbabdf3b2653cb36fc885c103b4715df17aa19f45435c9` / `00d8a5f446e16853c48000ef7c45352f896d9d580481baa3a4f3dd07f1afa3a9`
- path_exit_k3_t025 A/B sha256 `1d49b7d3b4b8ee718fd93f93481200076047ec4a60d145e4d9d35a149997a825` / `607aaa353e6f94f1846920b8df1c4a9af164b9ca7a3a8efc91a4665e0a43db06`

## Gate 1
{
  "A": {
    "n_U3": 117,
    "n_H3": 71,
    "n_W3": 37,
    "n_defined": 117,
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
    "EPS_SIT": 0.05,
    "MFE_LIFE": 0.25
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
    "EPS_SIT": 0.05,
    "MFE_LIFE": 0.25
  },
  "SHAPE_SPLIT": {
    "tag": "SHAPE_NONE",
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
- skipped_because `gate1_tag=SHAPE_NONE` / replay_ran `false` / optimizer_steps `0`
- ContextVar set/reset in try/finally : yes
- PATH_EXIT_K3_SHADOW remained False : yes

## Flags
{
  "source": "path_early_measure",
  "EPS_SIT": 0.05,
  "MFE_LIFE": 0.25,
  "T_LOCK_HIST": -0.04787176712367987,
  "T_FP_HIST": -0.25,
  "skip_replay": false,
  "replay_ran": false,
  "gate1_tag": "SHAPE_NONE",
  "A_measure": {
    "n_U3": 117,
    "n_H3": 71,
    "n_W3": 37,
    "n_defined": 117,
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
    "EPS_SIT": 0.05,
    "MFE_LIFE": 0.25
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
    "EPS_SIT": 0.05,
    "MFE_LIFE": 0.25
  },
  "A": {
    "n_exit": 0,
    "S_MISSING_HOOK": true,
    "S_HARM": false,
    "HOLE_MOVED": false,
    "tag": "S_MISSING",
    "law": "NONE",
    "baseline": {
      "n_H": 0,
      "mean_r_H": 0.0,
      "n_W": 0,
      "mean_r_W": 0.0,
      "n_policy": 0,
      "wr_policy": 0.0,
      "mean_r_policy": 0.0,
      "n_still_open_at_3": 0,
      "present": false
    }
  },
  "B": {
    "n_exit": 0,
    "S_MISSING_HOOK": true,
    "S_HARM": false,
    "HOLE_MOVED": false,
    "tag": "S_MISSING",
    "law": "NONE",
    "baseline": {
      "n_H": 0,
      "mean_r_H": 0.0,
      "n_W": 0,
      "mean_r_W": 0.0,
      "n_policy": 0,
      "wr_policy": 0.0,
      "mean_r_policy": 0.0,
      "n_still_open_at_3": 0,
      "present": false
    }
  },
  "tag": "SHAPE_NONE",
  "HOLE_MOVED_A": false,
  "HOLE_MOVED_B": false,
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
  "mean_stamped_shape_A": null,
  "overall": "GRIND_REGRESS_AWAKENING_OPEN PATH_SHAPE_K3_DEAD SHADOW_MEASURE"
}

## n_exit vs T-family clone
- A n_exit `0` / mean stamped shape `None` / threshold present `False`

## Honesty
#27 T_LOCK A HOLE_MOVED; B mean_r worse. Promoting T_LOCK is forbidden.
#28 T_FP=-0.25 TRANSFER_FAIL. k=3 R-threshold family exhausted as a controller.
This ticket locks EPS_SIT=0.05 and MFE_LIFE=0.25 a priori (parking + quarter-life), not A/B-fitted.
ContextVar PATH_SHAPE_K3_SHADOW armed only on Gate 2. PATH_EXIT_K3_SHADOW stayed False.
Median not recomputed. No T compare in should_path_shape_k3_dead.
Gate 1 tag=SHAPE_NONE lift A/B=0.0/0.0
Gate 2 skip_replay=false ran=false n_exit A/B=0/0
n_H A base→shape=0→0 B 0→0
mean_r A base→shape=0.0→0.0 B 0.0→0.0
HOLE_MOVED A/B=false/false.
Tag: SHAPE_NONE.
Law: SHADOW default off | NONE.
Playground: no.
Evolution Proof stamped: False.
REAL: no.

## Protocol inspect
{
  "eps_sit": "lumina_core/birth/awakening_path_shape_k3_dead.py:44",
  "mfe_life": "lumina_core/birth/awakening_path_shape_k3_dead.py:45",
  "t_lock": "lumina_core/birth/awakening_path_exit_k3.py:16",
  "t_fp": "lumina_core/birth/awakening_path_exit_k3_t025.py:1",
  "shape_shadow_default": "lumina_core/birth/awakening_path_shape_k3_dead.py:57",
  "t_shadow_default": "lumina_core/birth/awakening_path_exit_k3.py:22",
  "should_no_t_compare": "lumina_core/birth/awakening_path_shape_k3_dead.py:122",
  "after_open_telem": "lumina_core/birth/awakening_path_exit_k3_hook.py:69",
  "peek_no_stash_write": "lumina_core/birth/awakening_path_shape_k3_dead_peek.py:10",
  "shape_set_eval": "lumina_core/birth/awakening_path_shape_k3_dead_eval.py:356",
  "shape_set_run": "lumina_core/birth/awakening_path_shape_k3_dead_run.py:165",
  "t_shadow_not_set_true_eval": "lumina_core/birth/awakening_path_shape_k3_dead_eval.py:ok",
  "t_shadow_not_set_true_run": "lumina_core/birth/awakening_path_shape_k3_dead_run.py:ok",
  "license_shape_both": "lumina_core/birth/awakening_path_shape_k3_dead_flags.py:139",
  "license_transfer_both": "lumina_core/birth/awakening_path_shape_k3_dead_flags.py:162",
  "transfer_ok_requires_shape_split": "lumina_core/birth/awakening_path_shape_k3_dead_run.py:91",
  "forbidden_write_path_early_jsonl": "lumina_core/birth/awakening_path_shape_k3_dead.py:89",
  "forbidden_write_path_exit_k3_t025_jsonl": "lumina_core/birth/awakening_path_shape_k3_dead.py:53",
  "evaluate_only_learn": "lumina_core/birth/awakening_grind.py:104",
  "parent_sha_const": "lumina_core/birth/awakening_path_exit_k3.py:30",
  "gitpython_pin": "requirements-core.txt:140",
  "codecov_patch_50": "codecov.yml:16",
  "mutual_exclusion": "lumina_core/birth/awakening_path_exit_k3_hook.py:81",
  "missing_sites": [],
  "gate0_complete": true
}

## Tm / T0 / T1 / T2 / T3 / T4
{
  "A": {
    "n_U3": 117,
    "n_H3": 71,
    "n_W3": 37,
    "n_defined": 117,
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
    "EPS_SIT": 0.05,
    "MFE_LIFE": 0.25
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
    "EPS_SIT": 0.05,
    "MFE_LIFE": 0.25
  }
}
{
  "A": {
    "n_all": 0,
    "n_policy": 0,
    "n_plant": 0,
    "wr_policy": 0.0,
    "mean_r_policy": 0.0,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "",
    "price_sha16": "",
    "optimizer_steps": 0,
    "hook_enabled": false,
    "shape_enabled": false,
    "T_family_enabled": false,
    "mean_stamped_shape": null,
    "n_exit": 0,
    "skip_replay": false,
    "replay_ran": false,
    "source": "awakening_path_shape_k3_dead"
  },
  "B": {
    "n_all": 0,
    "n_policy": 0,
    "n_plant": 0,
    "wr_policy": 0.0,
    "mean_r_policy": 0.0,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "",
    "price_sha16": "",
    "optimizer_steps": 0,
    "hook_enabled": false,
    "shape_enabled": false,
    "T_family_enabled": false,
    "mean_stamped_shape": null,
    "n_exit": 0,
    "skip_replay": false,
    "replay_ran": false,
    "source": "awakening_path_shape_k3_dead"
  }
}
{
  "A": {
    "n_U": 0,
    "n_H": 0,
    "n_W": 0,
    "n_exit": 0,
    "mean_r_exit": 0.0,
    "wr_exit": 0.0,
    "wr_policy": 0.0,
    "mean_r_policy": 0.0
  },
  "B": {
    "n_U": 0,
    "n_H": 0,
    "n_W": 0,
    "n_exit": 0,
    "mean_r_exit": 0.0,
    "wr_exit": 0.0,
    "wr_policy": 0.0,
    "mean_r_policy": 0.0
  }
}
{
  "A": {
    "n_H_base": 0,
    "n_H_shape": 0,
    "delta_n_H": 0,
    "n_W_base": 0,
    "n_W_shape": 0,
    "delta_n_W": 0,
    "wr_policy_base": 0.0,
    "wr_policy_shape": 0.0,
    "delta_wr": 0.0,
    "mean_r_policy_base": 0.0,
    "mean_r_policy_shape": 0.0,
    "delta_mean_r_policy": 0.0,
    "HOLE_MOVED": false
  },
  "B": {
    "n_H_base": 0,
    "n_H_shape": 0,
    "delta_n_H": 0,
    "n_W_base": 0,
    "n_W_shape": 0,
    "delta_n_W": 0,
    "wr_policy_base": 0.0,
    "wr_policy_shape": 0.0,
    "delta_wr": 0.0,
    "mean_r_policy_base": 0.0,
    "mean_r_policy_shape": 0.0,
    "delta_mean_r_policy": 0.0,
    "HOLE_MOVED": false
  }
}
{
  "A": {
    "n_exit_k27": 0,
    "n_exit_t025": 0,
    "n_exit_shape": 0
  },
  "B": {
    "n_exit_k27": 0,
    "n_exit_t025": 0,
    "n_exit_shape": 0
  }
}
{
  "grind_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/grind_A_close_ledger.jsonl",
    "n": 83,
    "mean_r": -1.0377626965532611
  },
  "grind_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/grind_B_close_ledger.jsonl",
    "n": 94,
    "mean_r": -1.0631267323835003
  },
  "select_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/select_A_close_ledger.jsonl",
    "n": 79,
    "mean_r": -1.0377639065293784
  },
  "select_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/select_B_close_ledger.jsonl",
    "n": 75,
    "mean_r": -1.0675576786404861
  },
  "hole_tax_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/hole_tax_A_close_ledger.jsonl",
    "n": 86,
    "mean_r": -1.0377589113836108
  },
  "hole_tax_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/hole_tax_B_close_ledger.jsonl",
    "n": 87,
    "mean_r": -1.0515524666548113
  },
  "entry_autopsy_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/entry_autopsy_A_close_ledger.jsonl",
    "n": 76,
    "mean_r": -1.0520731660642308
  },
  "entry_autopsy_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/entry_autopsy_B_close_ledger.jsonl",
    "n": 82,
    "mean_r": -1.0770073952838481
  },
  "open_split_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/open_split_A_close_ledger.jsonl",
    "n": 81,
    "mean_r": -1.0377542959638937
  },
  "open_split_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/open_split_B_close_ledger.jsonl",
    "n": 82,
    "mean_r": -1.0515284303747383
  },
  "policy_signal_A": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/policy_signal_A_close_ledger.jsonl",
    "n": 85,
    "mean_r": -1.054127657831403
  },
  "policy_signal_B": {
    "absent": false,
    "path": "reports/birth_cloud_run/artifacts/policy_signal_B_close_ledger.jsonl",
    "n": 90,
    "mean_r": -1.0515406122528288
  },
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
    "lumina_core/birth/awakening_select_path.py",
    "lumina_core/birth/awakening_select_run.py"
  ],
  "playground": false
}

