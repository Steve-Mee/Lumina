# AWAKENING_PATH_SHAPE_K3_DEAD_VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN PATH_SHAPE_K3_DEAD SHADOW_MEASURE`
**Date:** 2026-09-04T06:30:35.056964+00:00
**Evaluated zip sha256:** `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
**optimizer_steps:** `0`
**skip_replay:** `false`
**replay_ran:** `false`
**EPS_SIT:** `0.05`
**MFE_LIFE:** `0.25`
**gate1_tag:** `SHAPE_NONE`
**n_exit A/B:** `0` / `0`
**n_H A base→shape:** `0` → `0`
**n_H B base→shape:** `0` → `0`
**mean_r A base→shape:** `0.0` → `0.0`
**mean_r B base→shape:** `0.0` → `0.0`
**HOLE_MOVED A/B:** `False` / `False`
**Tag:** `SHAPE_NONE`
**Law:** `NONE`
**Family:** `PATH_SHAPE:P_K3_DEAD`
**Evolution Proof stamped:** `False`
**Playground:** `no`
**REAL:** `no`

### Tm — Gate 1 measure
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

### T0 — identity
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

### T1 — U / H / W / exit
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

### T2 — compare vs path_early
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

### T3 — vs #27 / #28 n_exit
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

### T4 — read-only prior hole
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

### Honesty
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

Playground does not open. No learn(). Hook default off. Evolution Proof stamped: False.

