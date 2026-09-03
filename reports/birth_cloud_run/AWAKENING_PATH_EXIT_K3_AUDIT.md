# AWAKENING_PATH_EXIT_K3_AUDIT

## Gate 0
- origin/main SHA `334e367ffeec8fecf01b70f86b1dd84952064ebf` (PR #26 merge `334e367ffeec8fecf01b70f86b1dd84952064ebf`)
- parent_loaded: `True`
- date: `2026-09-03T21:10:28.031903+00:00`

## Flatten path (existing close physics)

{
  "force_flatten": "lumina_core/birth/sim_runner.py:_path_exit_k3_request",
  "plan_birth_exit_fill": "lumina_core/rl/gym_stop_fill.py:38",
  "close_reason": "force_exit + path_exit_k3 sidecar"
}

- T_LOCK `-0.04787176712367987` (PATH_EARLY / PATH_UNREAL_K3 leg A threshold). Not recomputed.
- k=3 only. Plant / FORCE_OPEN never flattened.

## Protocol inspect

{
  "t_lock": "lumina_core/birth/awakening_path_exit_k3.py:16",
  "should_path_exit_k3": "lumina_core/birth/awakening_path_exit_k3.py:106",
  "hook_default_false": "lumina_core/birth/awakening_grind_run.py:170",
  "snapshot_unreal_key": "lumina_core/birth/sim_runner_entry_telem.py:18",
  "flatten_request_site": "lumina_core/birth/sim_runner.py:594",
  "path_exit_k3_ledger_key": "lumina_core/birth/s5_close_ledger_trace.py:88",
  "hole_moved_def": "lumina_core/birth/awakening_path_exit_k3_flags.py:32",
  "s_harm_def": "lumina_core/birth/awakening_path_exit_k3_flags.py:28",
  "parent_sha_const": "lumina_core/birth/awakening_path_exit_k3.py:29",
  "evaluate_only_learn": "lumina_core/birth/awakening_grind.py:104",
  "forbidden_write_path_early_jsonl": "lumina_core/birth/awakening_path_exit_k3.py:36",
  "run_evaluate_only_hook_true": "lumina_core/birth/awakening_path_exit_k3_eval.py:118",
  "gitpython_pin": "requirements-core.txt:140",
  "codecov_patch_50": "codecov.yml:16",
  "missing_sites": [],
  "gate0_complete": true
}

## Flags

{
  "skip_replay": false,
  "replay_ran": true,
  "A": {
    "n_policy": 150,
    "n_U": 125,
    "n_H": 40,
    "mean_r_H": -1.037766231090237,
    "n_W": 29,
    "mean_r_W": 1.2471510660387781,
    "n_exit": 50,
    "mean_r_exit": -0.46042949993630616,
    "wr_exit": 0.0,
    "wr_policy": 0.26,
    "mean_r_policy": -0.22990106636644933,
    "mean_usd_policy": -25.956150023090828,
    "S_MISSING_HOOK": false,
    "S_HARM": false,
    "HOLE_MOVED": true,
    "S_THIN": false,
    "tag": "HOLE_MOVED",
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
    "n_U": 132,
    "n_H": 42,
    "mean_r_H": -1.0515355822068149,
    "n_W": 31,
    "mean_r_W": 1.1535368865863371,
    "n_exit": 57,
    "mean_r_exit": -0.4658773451340696,
    "wr_exit": 0.0,
    "wr_policy": 0.22666666666666666,
    "mean_r_policy": -0.3266154295192,
    "mean_usd_policy": -27.019042717225872,
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
  "tag": "HOLE_MOVED",
  "law": "SHADOW",
  "licensed_next_family": "PATH_EXIT:P_K3_UNREAL_RED",
  "gate1": "SHADOW",
  "T_LOCK": -0.04787176712367987,
  "optimizer_steps": 0,
  "evaluated_zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "overall": "GRIND_REGRESS_AWAKENING_OPEN PATH_EXIT_K3_SHADOW SHADOW_MEASURE"
}

## Honesty

PR #26 licensed PATH_EXIT:P_K3_UNREAL_RED with law NONE.
This ticket shadows flatten-at-3 at T_LOCK=-0.04787176712367987.
k=5 not used. Median not recomputed on this book.
Replay skip_replay=false n_exit A/B=50/57 n_H A base→shadow=78→40.
Tag: HOLE_MOVED.
Law shipped: SHADOW (default off).
Playground: no.
Evolution Proof stamped: False.
REAL: no.

## T0 / T1 / T2 / T3 / T4 / T5

{
  "A": {
    "n_all": 230,
    "n_policy": 150,
    "n_plant": 80,
    "wr_policy": 0.26,
    "mean_r_policy": -0.22990106636644933,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "aff3cb1e3a6f5014",
    "optimizer_steps": 0,
    "hook_enabled": true,
    "n_exit": 50,
    "skip_replay": false,
    "replay_ran": true,
    "source": "awakening_path_exit_k3"
  },
  "B": {
    "n_all": 188,
    "n_policy": 150,
    "n_plant": 38,
    "wr_policy": 0.22666666666666666,
    "mean_r_policy": -0.3266154295192,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "e51ce9b724515e2e",
    "optimizer_steps": 0,
    "hook_enabled": true,
    "n_exit": 57,
    "skip_replay": false,
    "replay_ran": true,
    "source": "awakening_path_exit_k3"
  }
}
{
  "A": {
    "U": {
      "n": 125,
      "wr": 0.232,
      "mean_r": -0.2680949519626588,
      "mean_usd": -30.254143790632767
    },
    "H": {
      "n": 40,
      "wr": 0.0,
      "mean_r": -1.037766231090237,
      "mean_usd": -117.05930473709375
    },
    "W": {
      "n": 29,
      "wr": 1.0,
      "mean_r": 1.2471510660387781,
      "mean_usd": 140.58576737148914
    },
    "n_U": 125,
    "n_H": 40,
    "n_W": 29,
    "n_exit": 50,
    "mean_r_exit": -0.46042949993630616,
    "wr_exit": 0.0
  },
  "B": {
    "U": {
      "n": 132,
      "wr": 0.23484848484848486,
      "mean_r": -0.28077952990998206,
      "mean_usd": -23.2360595571014
    },
    "H": {
      "n": 42,
      "wr": 0.0,
      "mean_r": -1.0515355822068149,
      "mean_usd": -86.92143306690191
    },
    "W": {
      "n": 31,
      "wr": 1.0,
      "mean_r": 1.1535368865863371,
      "mean_usd": 95.27723160812579
    },
    "n_U": 132,
    "n_H": 42,
    "n_W": 31,
    "n_exit": 57,
    "mean_r_exit": -0.4658773451340696,
    "wr_exit": 0.0
  }
}
{
  "A": {
    "n_H_base": 78,
    "n_H_shadow": 40,
    "delta_n_H": -38,
    "mean_r_H_base": -1.0375115459769815,
    "mean_r_H_shadow": -1.037766231090237,
    "n_W_base": 39,
    "n_W_shadow": 29,
    "delta_n_W": -10,
    "wr_policy_base": 0.30666666666666664,
    "wr_policy_shadow": 0.26,
    "mean_r_policy_base": -0.3092697822118258,
    "mean_r_policy_shadow": -0.22990106636644933,
    "delta_mean_r_policy": 0.0793687158453765
  },
  "B": {
    "n_H_base": 83,
    "n_H_shadow": 42,
    "delta_n_H": -41,
    "mean_r_H_base": -1.0515276607883177,
    "mean_r_H_shadow": -1.0515355822068149,
    "n_W_base": 42,
    "n_W_shadow": 31,
    "delta_n_W": -11,
    "wr_policy_base": 0.36,
    "wr_policy_shadow": 0.22666666666666666,
    "mean_r_policy_base": -0.17973357939421974,
    "mean_r_policy_shadow": -0.3266154295192,
    "delta_mean_r_policy": -0.14688185012498023
  }
}
{
  "A": {
    "paper_drop_H": 43,
    "paper_drop_W": 12,
    "paper_n_exit_scale": 55,
    "n_exit_live": 50,
    "scale_fail": false,
    "why": "n_exit within 2\u00d7 paper counterfactual scale"
  },
  "B": {
    "paper_drop_H": 43,
    "paper_drop_W": 12,
    "paper_n_exit_scale": 55,
    "n_exit_live": 57,
    "scale_fail": false,
    "why": "n_exit within 2\u00d7 paper counterfactual scale"
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
  "path_unreal_k3_A": {
    "absent": true,
    "path": "reports/birth_cloud_run/artifacts/path_unreal_k3_A_close_ledger.jsonl"
  },
  "path_unreal_k3_B": {
    "absent": true,
    "path": "reports/birth_cloud_run/artifacts/path_unreal_k3_B_close_ledger.jsonl"
  }
}
{
  "A": {
    "join_absent": false,
    "n_exit": 50,
    "n_joined": 3,
    "would_H": 2,
    "would_W": 1,
    "share_would_H": 0.04,
    "share_would_W": 0.02
  },
  "B": {
    "join_absent": false,
    "n_exit": 57,
    "n_joined": 2,
    "would_H": 1,
    "would_W": 0,
    "share_would_H": 0.017543859649122806,
    "share_would_W": 0.0
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
    "lumina_core/birth/awakening_path_unreal_k3_report.py",
    "lumina_core/birth/awakening_select_path.py",
    "lumina_core/birth/awakening_select_run.py"
  ],
  "playground": false,
  "evolution_proof_stamped": false
}

