# AWAKENING OPEN POLICY SIGNAL AUDIT

## Mission

Among policy trades that OPEN in NEUTRAL, does the frozen π* value-head / entropy / action-margin knowable at the open bar separate `stop × close NEUTRAL` (hole H) from +R closes (winners W)?
Measure-only. Gate 1 law NONE. No open-mask. No learn().
**Date:** 2026-09-03T17:11:13.011635+00:00
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
  "evaluate_only_learn": "lumina_core/birth/awakening_grind.py:104",
  "last_open_signal": "lumina_core/birth/awakening_grind.py:100",
  "parent_sha_const": "lumina_core/birth/awakening_open_policy_signal.py:41",
  "p_value": "lumina_core/birth/awakening_open_policy_signal_flags.py:22",
  "p_entropy": "lumina_core/birth/awakening_open_policy_signal_flags.py:23",
  "p_action_margin": "lumina_core/birth/awakening_open_policy_signal_flags.py:24",
  "extract_policy_signals": "lumina_core/birth/policy_signal_extract.py:154",
  "s_split": "lumina_core/birth/awakening_open_policy_signal_flags.py:151",
  "s_missing_signal": "lumina_core/birth/awakening_open_policy_signal_flags.py:142",
  "s_missing_u": "lumina_core/birth/awakening_open_policy_signal_flags.py:14",
  "licensed_next_family_h_none": "lumina_core/birth/awakening_open_policy_signal_flags.py:36",
  "license_never_open_decision": "lumina_core/birth/awakening_open_policy_signal_flags.py:ok",
  "overall_inconclusive": "lumina_core/birth/awakening_open_policy_signal.py:210",
  "isolated_workspace": "lumina_core/birth/awakening_open_policy_signal.py:90",
  "forbidden_writes": "lumina_core/birth/awakening_open_policy_signal.py:60",
  "forbidden_open_split_jsonl": "lumina_core/birth/awakening_open_policy_signal.py:80",
  "select_step_r": "lumina_core/birth/awakening_select_env.py:231",
  "close_ledger_open_policy_value": "lumina_core/birth/s5_close_ledger_trace.py:77",
  "close_ledger_open_policy_entropy": "lumina_core/birth/s5_close_ledger_trace.py:78",
  "close_ledger_open_policy_action_margin": "lumina_core/birth/s5_close_ledger_trace.py:79",
  "close_ledger_open_policy_p_chosen": "lumina_core/birth/s5_close_ledger_trace.py:80",
  "telem_open_policy_value": "lumina_core/birth/sim_runner_entry_telem.py:239",
  "telem_open_policy_entropy": "lumina_core/birth/sim_runner_entry_telem.py:240",
  "telem_open_policy_action_margin": "lumina_core/birth/sim_runner_entry_telem.py:241",
  "telem_open_policy_p_chosen": "lumina_core/birth/sim_runner_entry_telem.py:242",
  "sim_runner_last_open_signal": "lumina_core/birth/sim_runner.py:634",
  "run_evaluate_only_call": "lumina_core/birth/awakening_open_policy_signal_run.py:123",
  "gitpython_pin": "requirements-core.txt:140",
  "codecov_patch_50": "codecov.yml:16",
  "live_policy_signal_stash_attr_paths": {
    "open_policy_value": "policy.predict_values(obs) via extract_policy_signals",
    "open_policy_entropy": "dist.entropy() via extract_policy_signals",
    "open_policy_p_chosen": "P(taken action) via extract_policy_signals",
    "open_policy_action_margin": "p_chosen - max(p_other) via extract_policy_signals"
  },
  "missing_sites": [],
  "gate0_complete": true
}

## Policy signal extraction sites

| key | extraction path | A | B |
|-----|-----------------|---|---|
| `open_policy_value` | `policy.predict_values(obs) via extract_policy_signals` | n/a | n/a |
| `open_policy_entropy` | `dist.entropy() via extract_policy_signals` | n/a | n/a |
| `open_policy_p_chosen` | `P(taken action) via extract_policy_signals` | n/a | n/a |
| `open_policy_action_margin` | `p_chosen - max(p_other) via extract_policy_signals` | n/a | n/a |

## Adaptive thresholds (median-split from universe)

- A thresholds: `{"value_median": 1.5816690921783447, "entropy_median": 5.686735153198242, "action_margin_median": 0.3}`
- B thresholds: `{"value_median": 1.6298996210098267, "entropy_median": 5.686735153198242, "action_margin_median": 0.3}`

## Fixture reuse (A/B ticks_sha16, price_sha16, reused_manifest)

- A ticks_sha16=`7e86c2bb1c71d514` price_sha16=`aff3cb1e3a6f5014` reused_manifest=`False`
- B ticks_sha16=`7e86c2bb1c71d514` price_sha16=`e51ce9b724515e2e` reused_manifest=`False`

## Evaluate-only call (run_evaluate_only kwargs, optimizer_steps)

call site: `lumina_core/birth/awakening_open_policy_signal_run.py:123`
runtime=`select_runtime()`, ledger_source=`awakening_open_policy_signal`, exploration_steps=0 (via s5_envelope_kwargs), TRAIN=False.
**optimizer_steps:** `0` (A t0=0 B t0=0)

## T0 identity + wire-vs-autopsy-A

{
  "A": {
    "n_all": 217,
    "n_policy": 150,
    "n_plant": 67,
    "wr_policy": 0.29333333333333333,
    "mean_r_policy": -0.3349312319485545,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "aff3cb1e3a6f5014",
    "optimizer_steps": 0
  },
  "B": {
    "n_all": 174,
    "n_policy": 150,
    "n_plant": 24,
    "wr_policy": 0.3333333333333333,
    "mean_r_policy": -0.2693545645413111,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "e51ce9b724515e2e",
    "optimizer_steps": 0
  }
}

Wire vs OPEN_SPLIT A: wr_policy baseline 0.34 n_policy 150. AND-stop fires only if both deltas exceed 0.03 / 15.

## T1 U / H / W

{
  "A": {
    "U": {
      "n": 132,
      "wr": 0.29545454545454547,
      "mean_r": -0.33123892858717613,
      "mean_usd": -37.62412093123465
    },
    "H": {
      "n": 80,
      "wr": 0.0,
      "mean_r": -1.0551510239973898,
      "mean_usd": -119.01607193868934
    },
    "W": {
      "n": 39,
      "wr": 1.0,
      "mean_r": 1.3046678926990323,
      "mean_usd": 147.06132467002394
    },
    "n_U": 132,
    "n_H": 80,
    "n_W": 39,
    "share_H": 0.6060606060606061,
    "share_W": 0.29545454545454547
  },
  "B": {
    "U": {
      "n": 131,
      "wr": 0.3511450381679389,
      "mean_r": -0.22460621145309398,
      "mean_usd": -18.58933116370701
    },
    "H": {
      "n": 79,
      "wr": 0.0,
      "mean_r": -1.0515374855124344,
      "mean_usd": -86.91837479677729
    },
    "W": {
      "n": 46,
      "wr": 1.0,
      "mean_r": 1.284970781174071,
      "mean_usd": 106.14276146365653
    },
    "n_U": 131,
    "n_H": 79,
    "n_W": 46,
    "share_H": 0.6030534351145038,
    "share_W": 0.3511450381679389
  }
}

## T1b raw signal distributions

{
  "A": {
    "open_policy_value": {
      "U": {
        "n_defined": 132,
        "missing_share": 0.0,
        "mean": 1.5897773124954917,
        "median": 1.5816690921783447,
        "p25": 1.5816690921783447,
        "p75": 1.5816690921783447
      },
      "H": {
        "n_defined": 80,
        "missing_share": 0.0,
        "mean": 1.5905881345272064,
        "median": 1.5816690921783447,
        "p25": 1.5816690921783447,
        "p75": 1.5816690921783447
      },
      "W": {
        "n_defined": 39,
        "missing_share": 0.0,
        "mean": 1.590816827920767,
        "median": 1.5816690921783447,
        "p25": 1.5816690921783447,
        "p75": 1.5816690921783447
      }
    },
    "open_policy_entropy": {
      "U": {
        "n_defined": 132,
        "missing_share": 0.0,
        "mean": 5.686735153198242,
        "median": 5.686735153198242,
        "p25": 5.686735153198242,
        "p75": 5.686735153198242
      },
      "H": {
        "n_defined": 80,
        "missing_share": 0.0,
        "mean": 5.686735153198242,
        "median": 5.686735153198242,
        "p25": 5.686735153198242,
        "p75": 5.686735153198242
      },
      "W": {
        "n_defined": 39,
        "missing_share": 0.0,
        "mean": 5.686735153198242,
        "median": 5.686735153198242,
        "p25": 5.686735153198242,
        "p75": 5.686735153198242
      }
    },
    "open_policy_action_margin": {
      "U": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      },
      "H": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      },
      "W": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      }
    },
    "open_policy_p_chosen": {
      "U": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      },
      "H": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      },
      "W": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      }
    }
  },
  "B": {
    "open_policy_value": {
      "U": {
        "n_defined": 131,
        "missing_share": 0.0,
        "mean": 1.575750523851118,
        "median": 1.6298996210098267,
        "p25": 1.4981027841567993,
        "p75": 1.6298996210098267
      },
      "H": {
        "n_defined": 79,
        "missing_share": 0.0,
        "mean": 1.5690786898890627,
        "median": 1.557984709739685,
        "p25": 1.4981027841567993,
        "p75": 1.6298996210098267
      },
      "W": {
        "n_defined": 46,
        "missing_share": 0.0,
        "mean": 1.5874394126560376,
        "median": 1.6298996210098267,
        "p25": 1.557984709739685,
        "p75": 1.6298996210098267
      }
    },
    "open_policy_entropy": {
      "U": {
        "n_defined": 131,
        "missing_share": 0.0,
        "mean": 5.686735153198242,
        "median": 5.686735153198242,
        "p25": 5.686735153198242,
        "p75": 5.686735153198242
      },
      "H": {
        "n_defined": 79,
        "missing_share": 0.0,
        "mean": 5.686735153198242,
        "median": 5.686735153198242,
        "p25": 5.686735153198242,
        "p75": 5.686735153198242
      },
      "W": {
        "n_defined": 46,
        "missing_share": 0.0,
        "mean": 5.686735153198242,
        "median": 5.686735153198242,
        "p25": 5.686735153198242,
        "p75": 5.686735153198242
      }
    },
    "open_policy_action_margin": {
      "U": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      },
      "H": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      },
      "W": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      }
    },
    "open_policy_p_chosen": {
      "U": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      },
      "H": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      },
      "W": {
        "n_defined": 0,
        "missing_share": 1.0,
        "mean": 0.0,
        "median": 0.0,
        "p25": 0.0,
        "p75": 0.0
      }
    }
  }
}

## T2 policy candidate grid

{
  "A": {
    "P_VALUE": {
      "threshold": 1.5816690921783447,
      "n_defined": 132,
      "missing_share": 0.0,
      "cov_H": 0.85,
      "cov_W": 0.8461538461538461,
      "lift": 0.0038461538461538325,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "P_ENTROPY": {
      "threshold": 5.686735153198242,
      "n_defined": 132,
      "missing_share": 0.0,
      "cov_H": 1.0,
      "cov_W": 1.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "P_ACTION_MARGIN": {
      "threshold": 0.3,
      "n_defined": 0,
      "missing_share": 1.0,
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": true
    }
  },
  "B": {
    "P_VALUE": {
      "threshold": 1.6298996210098267,
      "n_defined": 131,
      "missing_share": 0.0,
      "cov_H": 1.0,
      "cov_W": 1.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "P_ENTROPY": {
      "threshold": 5.686735153198242,
      "n_defined": 131,
      "missing_share": 0.0,
      "cov_H": 1.0,
      "cov_W": 1.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "P_ACTION_MARGIN": {
      "threshold": 0.3,
      "n_defined": 0,
      "missing_share": 1.0,
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": true
    }
  }
}

## T3 paper counterfactual

{
  "A": {
    "P_VALUE": {
      "drop_H": 68.0,
      "drop_W": 33.0,
      "remaining_H": 12.0,
      "remaining_W": 6.0
    },
    "P_ENTROPY": {
      "drop_H": 80.0,
      "drop_W": 39.0,
      "remaining_H": 0.0,
      "remaining_W": 0.0
    },
    "P_ACTION_MARGIN": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 80.0,
      "remaining_W": 39.0
    }
  },
  "B": {
    "P_VALUE": {
      "drop_H": 79.0,
      "drop_W": 46.0,
      "remaining_H": 0.0,
      "remaining_W": 0.0
    },
    "P_ENTROPY": {
      "drop_H": 79.0,
      "drop_W": 46.0,
      "remaining_H": 0.0,
      "remaining_W": 0.0
    },
    "P_ACTION_MARGIN": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 79.0,
      "remaining_W": 46.0
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

## T5 opposite-tail (READ_ONLY_FLIP, cannot win)

{
  "A": {
    "P_VALUE": {
      "cov_H": 0.15,
      "cov_W": 0.15384615384615385,
      "lift": -0.0038461538461538602,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    },
    "P_ENTROPY": {
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    },
    "P_ACTION_MARGIN": {
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    }
  },
  "B": {
    "P_VALUE": {
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    },
    "P_ENTROPY": {
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    },
    "P_ACTION_MARGIN": {
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    }
  }
}

## Licensing decision (A SSOT)

**Tag:** `S_NONE`  **Winning P:** `none`  **Licensed next family:** `H_NONE`  **Gate 1 law:** `NONE`
External OPEN_SPLIT bits did not separate H from W (PR #23 S_NONE).
This ticket asked whether frozen π* internals at OPEN do.
Replay: skip_replay=false. n_U A/B = 132/131.
Winning tag: S_NONE.
Licensed next family: H_NONE.
Law shipped: NONE.
Playground: no.
Evolution Proof stamped: False.
REAL: no.

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

