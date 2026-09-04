# AWAKENING_PATH_EXIT_K3_T025_AUDIT

## Gate 0
- origin/main SHA `a694f3f55f4bc7f3bb5abf8fecc6d09481ec200e` (PR #27 merge `a694f3f55f4bc7f3bb5abf8fecc6d09481ec200e`)
- T_LOCK still -0.04787176712367987 : yes
- parent_loaded: `True`
- date: `2026-09-04T05:42:01.735584+00:00`

## Hook
- PATH_EXIT_K3_THRESHOLD file:line `lumina_core/birth/awakening_path_exit_k3.py:23`
- should_path_exit_k3 threshold read file:line `lumina_core/birth/awakening_path_exit_k3.py:136`
- after_open_telem file:line `lumina_core/birth/awakening_path_exit_k3_hook.py:62`
- flatten site file:line `lumina_core/birth/sim_runner.py:_path_exit_k3_request`

## Source
- parent sha256 `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
- path_early A/B sha256 `4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb` / `0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356`
- path_exit_k3 (#27) A/B sha256 `0618dae7b58342898edbabdf3b2653cb36fc885c103b4715df17aa19f45435c9` / `00d8a5f446e16853c48000ef7c45352f896d9d580481baa3a4f3dd07f1afa3a9` (must match pre-PR)

## Replay
- skip_replay `false` / replay_ran `true` / optimizer_steps `0`
- ContextVar set/reset in try/finally : yes

## Flags

{
  "source": "new_replay",
  "T_FP": -0.25,
  "T_LOCK_HIST": -0.04787176712367987,
  "skip_replay": false,
  "replay_ran": true,
  "A": {
    "n_policy": 150,
    "n_U": 126,
    "n_H": 53,
    "mean_r_H": -1.0377582972637858,
    "n_W": 36,
    "mean_r_W": 1.2401378841212107,
    "n_exit": 30,
    "mean_r_exit": -0.5326836110889991,
    "wr_exit": 0.0,
    "wr_policy": 0.28,
    "mean_r_policy": -0.29534249318344147,
    "mean_usd_policy": -33.38976877438935,
    "S_MISSING_HOOK": false,
    "S_HARM": false,
    "HOLE_MOVED": false,
    "S_THIN": false,
    "tag": "HOLE_INTACT",
    "law": "SHADOW",
    "family": "PATH_EXIT:P_K3_UNREAL_RED",
    "gate1": "SHADOW",
    "baseline": {
      "n_H": 78,
      "mean_r_H": -1.0375115459769815,
      "n_W": 39,
      "mean_r_W": 1.2679547632855288,
      "n_policy": 150,
      "wr_policy": 0.30666666666666664,
      "mean_r_policy": -0.3092697822118258,
      "n_still_open_at_3": 117,
      "present": true
    }
  },
  "B": {
    "n_policy": 150,
    "n_U": 122,
    "n_H": 46,
    "mean_r_H": -1.0515536997335326,
    "n_W": 31,
    "mean_r_W": 1.308286432601032,
    "n_exit": 36,
    "mean_r_exit": -0.5385975822386412,
    "wr_exit": 0.0,
    "wr_policy": 0.2866666666666667,
    "mean_r_policy": -0.23297568771778443,
    "mean_usd_policy": -19.273418310343057,
    "S_MISSING_HOOK": false,
    "S_HARM": false,
    "HOLE_MOVED": false,
    "S_THIN": false,
    "tag": "HOLE_INTACT",
    "law": "SHADOW",
    "family": "PATH_EXIT:P_K3_UNREAL_RED",
    "gate1": "SHADOW",
    "baseline": {
      "n_H": 83,
      "mean_r_H": -1.0515276607883177,
      "n_W": 42,
      "mean_r_W": 1.2600750691100193,
      "n_policy": 150,
      "wr_policy": 0.36,
      "mean_r_policy": -0.17973357939421974,
      "n_still_open_at_3": 126,
      "present": true
    }
  },
  "tag": "TRANSFER_FAIL",
  "HOLE_MOVED_A": false,
  "HOLE_MOVED_B": false,
  "law": "SHADOW",
  "licensed_next_family": "PATH_EXIT:P_K3_UNREAL_RED",
  "gate1": "SHADOW",
  "optimizer_steps": 0,
  "evaluated_zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "mean_stamped_threshold_A": -0.25,
  "mean_stamped_threshold_B": -0.25,
  "overall": "GRIND_REGRESS_AWAKENING_OPEN PATH_EXIT_K3_T025 SHADOW_MEASURE"
}

## n_exit vs T_LOCK clone
- A n_exit `30` / mean stamped threshold `-0.25`
- B n_exit `36` / mean stamped threshold `-0.25`

## Honesty

#27 T_LOCK A HOLE_MOVED; B mean_r worse. Promoting T_LOCK is forbidden.
This ticket locks T_FP=-0.25 a priori (quarter-stop), not B-fitted.
ContextVar PATH_EXIT_K3_THRESHOLD armed. Median not recomputed.
Replay skip_replay=false n_exit A/B=30/36 n_H A base→t025=78→53 B 83→46.
mean_r A base→t025=-0.3092697822118258→-0.29534249318344147 B -0.17973357939421974→-0.23297568771778443.
HOLE_MOVED A/B=false/false.
Tag: TRANSFER_FAIL.
Law: SHADOW default off.
Playground: no.
Evolution Proof stamped: False.
REAL: no.

## Protocol inspect

{
  "t_fp": "lumina_core/birth/awakening_path_exit_k3_t025.py:1",
  "t_lock": "lumina_core/birth/awakening_path_exit_k3.py:16",
  "threshold_var": "lumina_core/birth/awakening_path_exit_k3.py:23",
  "should_reads_threshold": "lumina_core/birth/awakening_path_exit_k3.py:136",
  "after_open_telem": "lumina_core/birth/awakening_path_exit_k3_hook.py:62",
  "shadow_set": "lumina_core/birth/awakening_path_exit_k3_t025_eval.py:381",
  "threshold_set": "lumina_core/birth/awakening_path_exit_k3_t025_eval.py:382",
  "license_transfer": "lumina_core/birth/awakening_path_exit_k3_t025_flags.py:56",
  "transfer_ok_requires_a_and_b": "lumina_core/birth/awakening_path_exit_k3_t025_flags.py:63",
  "forbidden_write_path_exit_k3_jsonl": "lumina_core/birth/awakening_path_exit_k3_t025.py:94",
  "evaluate_only_learn": "lumina_core/birth/awakening_grind.py:104",
  "parent_sha_const": "lumina_core/birth/awakening_path_exit_k3.py:30",
  "gitpython_pin": "requirements-core.txt:140",
  "codecov_patch_50": "codecov.yml:16",
  "run_shadow_set": "lumina_core/birth/awakening_path_exit_k3_t025_run.py:94",
  "run_threshold_set": "lumina_core/birth/awakening_path_exit_k3_t025_run.py:95",
  "missing_sites": [],
  "gate0_complete": true
}

## T0 / T1 / T2 / T3 / T4

{
  "A": {
    "n_all": 209,
    "n_policy": 150,
    "n_plant": 59,
    "wr_policy": 0.28,
    "mean_r_policy": -0.29534249318344147,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "aff3cb1e3a6f5014",
    "optimizer_steps": 0,
    "hook_enabled": true,
    "T_FP": -0.25,
    "mean_stamped_threshold": -0.25,
    "n_exit": 30,
    "skip_replay": false,
    "replay_ran": true,
    "source": "awakening_path_exit_k3_t025"
  },
  "B": {
    "n_all": 182,
    "n_policy": 150,
    "n_plant": 32,
    "wr_policy": 0.2866666666666667,
    "mean_r_policy": -0.23297568771778443,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "e51ce9b724515e2e",
    "optimizer_steps": 0,
    "hook_enabled": true,
    "T_FP": -0.25,
    "mean_stamped_threshold": -0.25,
    "n_exit": 36,
    "skip_replay": false,
    "replay_ran": true,
    "source": "awakening_path_exit_k3_t025"
  }
}
{
  "A": {
    "U": {
      "n": 126,
      "wr": 0.2857142857142857,
      "mean_r": -0.2474740734765145,
      "mean_usd": -27.96979648590961
    },
    "H": {
      "n": 53,
      "wr": 0.0,
      "mean_r": -1.0377582972637858,
      "mean_usd": -117.08303063602844
    },
    "W": {
      "n": 36,
      "wr": 1.0,
      "mean_r": 1.2401378841212107,
      "mean_usd": 139.74993295834523
    },
    "n_U": 126,
    "n_H": 53,
    "n_W": 36,
    "n_exit": 30,
    "mean_r_exit": -0.5326836110889991,
    "wr_exit": 0.0,
    "wr_policy": 0.28,
    "mean_r_policy": -0.29534249318344147
  },
  "B": {
    "U": {
      "n": 122,
      "wr": 0.2540983606557377,
      "mean_r": -0.28024577918308824,
      "mean_usd": -23.179765552043072
    },
    "H": {
      "n": 46,
      "wr": 0.0,
      "mean_r": -1.0515536997335326,
      "mean_usd": -86.89234308800076
    },
    "W": {
      "n": 31,
      "wr": 1.0,
      "mean_r": 1.308286432601032,
      "mean_usd": 108.04986613500797
    },
    "n_U": 122,
    "n_H": 46,
    "n_W": 31,
    "n_exit": 36,
    "mean_r_exit": -0.5385975822386412,
    "wr_exit": 0.0,
    "wr_policy": 0.2866666666666667,
    "mean_r_policy": -0.23297568771778443
  }
}
{
  "A": {
    "n_H_base": 78,
    "n_H_t025": 53,
    "delta_n_H": -25,
    "mean_r_H_base": -1.0375115459769815,
    "mean_r_H_t025": -1.0377582972637858,
    "n_W_base": 39,
    "n_W_t025": 36,
    "delta_n_W": -3,
    "wr_policy_base": 0.30666666666666664,
    "wr_policy_t025": 0.28,
    "delta_wr": -0.026666666666666616,
    "mean_r_policy_base": -0.3092697822118258,
    "mean_r_policy_t025": -0.29534249318344147,
    "delta_mean_r_policy": 0.01392728902838436,
    "HOLE_MOVED": false
  },
  "B": {
    "n_H_base": 83,
    "n_H_t025": 46,
    "delta_n_H": -37,
    "mean_r_H_base": -1.0515276607883177,
    "mean_r_H_t025": -1.0515536997335326,
    "n_W_base": 42,
    "n_W_t025": 31,
    "delta_n_W": -11,
    "wr_policy_base": 0.36,
    "wr_policy_t025": 0.2866666666666667,
    "delta_wr": -0.0733333333333333,
    "mean_r_policy_base": -0.17973357939421974,
    "mean_r_policy_t025": -0.23297568771778443,
    "delta_mean_r_policy": -0.053242108323564685,
    "HOLE_MOVED": false
  }
}
{
  "A": {
    "n_exit_k27": 50,
    "n_exit_t025": 30,
    "delta_n_exit": -20,
    "k27_absent": false
  },
  "B": {
    "n_exit_k27": 57,
    "n_exit_t025": 36,
    "delta_n_exit": -21,
    "k27_absent": false
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
    "lumina_core/birth/awakening_path_unreal_k3_report.py",
    "lumina_core/birth/awakening_select_path.py",
    "lumina_core/birth/awakening_select_run.py"
  ],
  "playground": false,
  "evolution_proof_stamped": false
}

