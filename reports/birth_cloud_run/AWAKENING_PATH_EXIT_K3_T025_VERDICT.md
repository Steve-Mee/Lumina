# AWAKENING_PATH_EXIT_K3_T025_VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN PATH_EXIT_K3_T025 SHADOW_MEASURE`
**Date:** 2026-09-04T05:42:01.735584+00:00
**Evaluated zip sha256:** `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
**optimizer_steps:** `0`
**skip_replay:** `false`
**replay_ran:** `true`
**T_FP:** `-0.25`
**T_LOCK_HIST:** `-0.04787176712367987`
**n_exit A/B:** `30` / `36`
**mean stamped threshold A/B:** `-0.25` / `-0.25`
**n_H A base→t025:** `78` → `53`
**n_H B base→t025:** `83` → `46`
**mean_r A base→t025:** `-0.3092697822118258` → `-0.29534249318344147`
**mean_r B base→t025:** `-0.17973357939421974` → `-0.23297568771778443`
**S_MISSING_HOOK A/B:** `False` / `False`
**S_HARM A/B:** `False` / `False`
**HOLE_MOVED A/B:** `False` / `False`
**Tag:** `TRANSFER_FAIL`
**Law:** `SHADOW`
**Family:** `PATH_EXIT:P_K3_UNREAL_RED`
**Evolution Proof stamped:** `False`
**Playground:** `no`
**REAL:** `no`

### T0 — identity

| Leg | n_all | n_policy | n_plant | wr | mean_r | zip | ticks | price | hook | T | mean_stamped | n_exit | optimizer_steps |
|-----|-------|----------|---------|----|--------|-----|-------|-------|------|---|--------------|--------|-----------------|
| A | 209 | 150 | 59 | 0.28 | -0.29534249318344147 | 8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03 | 7e86c2bb1c71d514 | aff3cb1e3a6f5014 | True | -0.25 | -0.25 | 30 | 0 |
| B | 182 | 150 | 32 | 0.2866666666666667 | -0.23297568771778443 | 8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03 | 7e86c2bb1c71d514 | e51ce9b724515e2e | True | -0.25 | -0.25 | 36 | 0 |

### T1 — U / H / W / exit

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

### T2 — compare vs path_early

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

### T3 — vs #27 T_LOCK book

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
  }
}

### Honesty

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

Playground does not open. No learn(). Hook default off. Evolution Proof stamped: False.

