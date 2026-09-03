# AWAKENING OPEN POLICY SIGNAL AUDIT

## Mission

Among policy trades that OPEN in NEUTRAL, does the frozen π* value-head / entropy / action-margin knowable at the open bar separate `stop × close NEUTRAL` (hole H) from +R closes (winners W)?
Measure-only. Gate 1 law NONE. No open-mask. No learn().
**Date:** 2026-09-03T16:10:46.688259+00:00
**Gate 0 (PR #23 land):** `a9c5e32b10ed517c78091806b9f58c8e65a3f621`
**parent_loaded:** `True`

## Prior closed science (do not reopen)

- PR #22 ENTRY: hole already NEUTRAL at OPEN. Family OPEN_DECISION.
- PR #23 OPEN_SPLIT: five external open bits → S_NONE. Licensed H_NONE.
- This ticket: policy-internal signals at NEUTRAL-open.

## Frozen hashes (parent / control / hole-tax) + bytes

| Role | sha256 | bytes |
|------|--------|-------|
| PARENT / Birth-exit π* | `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` | 202268 |
| CONTROL / PR #20 child | `db7daf3b978fe80624608e27111627b5b9c3070e71118c66673df996123dd029` | 202271 |
| HOLE-TAX child | `ca2ae0e5fa6f0e54215fe6c833e2ebff608b5e99426a6e75ff5f7167d6bb0325` | 202271 |

## Gate 0 protocol dump (inspect_open_policy_signal_protocol)

{
  "evaluate_only_learn": "lumina_core/birth/awakening_grind.py:93",
  "parent_sha_const": "lumina_core/birth/awakening_open_policy_signal.py:42",
  "p_value": "lumina_core/birth/awakening_open_policy_signal_flags.py:22",
  "p_entropy": "lumina_core/birth/awakening_open_policy_signal_flags.py:23",
  "p_action_margin": "lumina_core/birth/awakening_open_policy_signal_flags.py:24",
  "extract_policy_signals": "lumina_core/birth/policy_signal_extract.py:18",
  "sim_runner_extract_call": "lumina_core/birth/sim_runner.py:633",
  "s_split": "lumina_core/birth/awakening_open_policy_signal_flags.py:120",
  "s_harm": "lumina_core/birth/awakening_open_policy_signal_flags.py:137",
  "isolated_workspace": "lumina_core/birth/awakening_open_policy_signal.py:91",
  "forbidden_writes": "lumina_core/birth/awakening_open_policy_signal.py:61",
  "select_step_r": "lumina_core/birth/awakening_select_env.py:231",
  "close_ledger_open_policy_value": "lumina_core/birth/s5_close_ledger_trace.py:77",
  "close_ledger_open_policy_entropy": "lumina_core/birth/s5_close_ledger_trace.py:78",
  "close_ledger_open_policy_action_margin": "lumina_core/birth/s5_close_ledger_trace.py:79",
  "telem_open_policy_value": "lumina_core/birth/sim_runner_entry_telem.py:20",
  "telem_open_policy_entropy": "lumina_core/birth/sim_runner_entry_telem.py:21",
  "telem_open_policy_action_margin": "lumina_core/birth/sim_runner_entry_telem.py:22",
  "run_evaluate_only_call": "lumina_core/birth/awakening_open_policy_signal_run.py:113",
  "gitpython_pin": "requirements-core.txt:140",
  "codecov_patch_50": "codecov.yml:16",
  "live_policy_signal_stash_attr_paths": {
    "open_policy_value": "policy.predict_values(obs) via extract_policy_signals",
    "open_policy_entropy": "dist.entropy() via extract_policy_signals",
    "open_policy_action_margin": "sorted(probs)[0]-sorted(probs)[1] via extract_policy_signals"
  },
  "missing_sites": [],
  "gate0_complete": true
}

## Policy signal extraction sites

| key | extraction path | A | B |
|-----|-----------------|---|---|
| `open_policy_value` | `policy.predict_values(obs) via extract_policy_signals` | n/a | n/a |
| `open_policy_entropy` | `dist.entropy() via extract_policy_signals` | n/a | n/a |
| `open_policy_action_margin` | `sorted(probs)[0]-sorted(probs)[1] via extract_policy_signals` | n/a | n/a |

## Adaptive thresholds (median-split from universe)

- A thresholds: `{"value_median": 0.0, "entropy_median": 0.0, "action_margin_median": 0.0}`
- B thresholds: `{"value_median": 0.0, "entropy_median": 0.0, "action_margin_median": 0.0}`

## Fixture reuse (A/B ticks_sha16, price_sha16, reused_manifest)

- A ticks_sha16=`` price_sha16=`` reused_manifest=`None`
- B ticks_sha16=`` price_sha16=`` reused_manifest=`None`

## Evaluate-only call (run_evaluate_only kwargs, optimizer_steps)

call site: `lumina_core/birth/awakening_open_policy_signal_run.py:113`
runtime=`select_runtime()`, ledger_source=`awakening_open_policy_signal`, exploration_steps=0 (via s5_envelope_kwargs), TRAIN=False.
**optimizer_steps:** `0` (A t0=0 B t0=0)

## T0 identity + wire-vs-autopsy-A

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
    "optimizer_steps": 0
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
    "optimizer_steps": 0
  }
}

Wire vs PR #22 autopsy A: wr_policy baseline 0.373 n_policy 150. AND-stop fires only if both deltas exceed 0.03 / 15.

## T1 U / H / W

{
  "A": {
    "U": {
      "n": 0,
      "wr": 0.0,
      "mean_r": 0.0,
      "mean_usd": 0.0
    },
    "H": {
      "n": 0,
      "wr": 0.0,
      "mean_r": 0.0,
      "mean_usd": 0.0
    },
    "W": {
      "n": 0,
      "wr": 0.0,
      "mean_r": 0.0,
      "mean_usd": 0.0
    },
    "n_U": 0,
    "n_H": 0,
    "n_W": 0,
    "share_H": 0.0,
    "share_W": 0.0
  },
  "B": {
    "U": {
      "n": 0,
      "wr": 0.0,
      "mean_r": 0.0,
      "mean_usd": 0.0
    },
    "H": {
      "n": 0,
      "wr": 0.0,
      "mean_r": 0.0,
      "mean_usd": 0.0
    },
    "W": {
      "n": 0,
      "wr": 0.0,
      "mean_r": 0.0,
      "mean_usd": 0.0
    },
    "n_U": 0,
    "n_H": 0,
    "n_W": 0,
    "share_H": 0.0,
    "share_W": 0.0
  }
}

## T2 policy candidate grid

{
  "A": {
    "P_VALUE": {
      "threshold": 0.0,
      "n_defined": 0,
      "missing_share": 0.0,
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "P_ENTROPY": {
      "threshold": 0.0,
      "n_defined": 0,
      "missing_share": 0.0,
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "P_ACTION_MARGIN": {
      "threshold": 0.0,
      "n_defined": 0,
      "missing_share": 0.0,
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    }
  },
  "B": {
    "P_VALUE": {
      "threshold": 0.0,
      "n_defined": 0,
      "missing_share": 0.0,
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "P_ENTROPY": {
      "threshold": 0.0,
      "n_defined": 0,
      "missing_share": 0.0,
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "P_ACTION_MARGIN": {
      "threshold": 0.0,
      "n_defined": 0,
      "missing_share": 0.0,
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    }
  }
}

## T3 paper counterfactual

{
  "A": {
    "P_VALUE": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 0.0,
      "remaining_W": 0.0
    },
    "P_ENTROPY": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 0.0,
      "remaining_W": 0.0
    },
    "P_ACTION_MARGIN": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 0.0,
      "remaining_W": 0.0
    }
  },
  "B": {
    "P_VALUE": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 0.0,
      "remaining_W": 0.0
    },
    "P_ENTROPY": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 0.0,
      "remaining_W": 0.0
    },
    "P_ACTION_MARGIN": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 0.0,
      "remaining_W": 0.0
    }
  }
}

## T4 read-only contrast

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
  }
}

## Licensing decision (A SSOT)

**Tag:** `S_MISSING`  **Winning P:** `none`  **Licensed next family:** `OPEN_DECISION`  **Gate 1 law:** `NONE`
No train law licensed.

## Forbidden-path grep (learn, training_reward, OPEN_FILTER controller)

{
  "hygiene_token_in_birth": [],
  "model_learn_in_birth": [
    "lumina_core/birth/awakening_hole_tax_path.py",
    "lumina_core/birth/awakening_hole_tax_run.py",
    "lumina_core/birth/awakening_open_policy_signal_report.py",
    "lumina_core/birth/awakening_open_split_report.py",
    "lumina_core/birth/awakening_select_path.py",
    "lumina_core/birth/awakening_select_run.py"
  ],
  "open_filter_controller": false
}

## Capital / autonomy / experiment

- **Capital:** SIM only. Exam dollars stay the fill. No mask on live participation.
- **Autonomy:** measurement compounds; the organism learns whether its own value-head distinguishes hole from winners at NEUTRAL-open.
- **Experiment:** one variable (policy-internal signal split inside NEUTRAL-open). External open features (PR #23) stay closed. Close-tax family stays closed. Blanket NEUTRAL-refuse stays forbidden.

