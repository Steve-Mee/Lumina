# AWAKENING_PATH_EXIT_K3_VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN PATH_EXIT_K3_SHADOW SHADOW_MEASURE`
**Date:** 2026-09-03T21:10:28.031903+00:00
**Evaluated zip sha256:** `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
**optimizer_steps:** `0`
**skip_replay:** `false`
**replay_ran:** `true`
**T_LOCK:** `-0.04787176712367987`
**n_exit A/B:** `50` / `57`
**n_H A base→shadow:** `78` → `40`
**S_MISSING_HOOK A/B:** `False` / `False`
**S_HARM A/B:** `False` / `False`
**HOLE_MOVED A/B:** `True` / `False`
**Tag:** `HOLE_MOVED`
**Law:** `SHADOW`
**Family:** `PATH_EXIT:P_K3_UNREAL_RED`
**Evolution Proof stamped:** `False`
**Playground:** `no`
**REAL:** `no`

### T0 — identity

| Leg | n_all | n_policy | n_plant | wr | mean_r | hook | n_exit | optimizer_steps |
|-----|-------|----------|---------|----|--------|------|--------|-----------------|
| A | 230 | 150 | 80 | 0.26 | -0.22990106636644933 | True | 50 | 0 |
| B | 188 | 150 | 38 | 0.22666666666666666 | -0.3266154295192 | True | 57 | 0 |

### T1 — U / H / W / exit

- A H `{'n': 40, 'wr': 0.0, 'mean_r': -1.037766231090237, 'mean_usd': -117.05930473709375}` W `{'n': 29, 'wr': 1.0, 'mean_r': 1.2471510660387781, 'mean_usd': 140.58576737148914}` n_exit=50 mean_r_exit=-0.46042949993630616 wr_exit=0.0
- B H `{'n': 42, 'wr': 0.0, 'mean_r': -1.0515355822068149, 'mean_usd': -86.92143306690191}` W `{'n': 31, 'wr': 1.0, 'mean_r': 1.1535368865863371, 'mean_usd': 95.27723160812579}` n_exit=57 mean_r_exit=-0.4658773451340696 wr_exit=0.0

### T2 — compare vs path_early

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

### T3 — paper vs live n_exit

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
  "path_unreal_k3_A": {
    "absent": true,
    "path": "reports/birth_cloud_run/artifacts/path_unreal_k3_A_close_ledger.jsonl"
  },
  "path_unreal_k3_B": {
    "absent": true,
    "path": "reports/birth_cloud_run/artifacts/path_unreal_k3_B_close_ledger.jsonl"
  }
}

### T5 — who got flattened

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

### Honesty

PR #26 licensed PATH_EXIT:P_K3_UNREAL_RED with law NONE.
This ticket shadows flatten-at-3 at T_LOCK=-0.04787176712367987.
k=5 not used. Median not recomputed on this book.
Replay skip_replay=false n_exit A/B=50/57 n_H A base→shadow=78→40.
Tag: HOLE_MOVED.
Law shipped: SHADOW (default off).
Playground: no.
Evolution Proof stamped: False.
REAL: no.

Playground does not open. No learn(). Hook default off. Evolution Proof stamped: False.

