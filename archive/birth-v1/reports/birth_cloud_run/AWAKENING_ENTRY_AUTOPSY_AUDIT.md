# AWAKENING ENTRY AUTOPSY AUDIT

**Date:** 2026-09-03T12:01:42.706157+00:00
**Engine:** BRO-v2 evaluate-only parent replay (no PPO update)
**Capital:** SIM / certified-shadow. REAL=no. NT=no.
**Evaluated zip sha256:** `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
**optimizer_steps:** `0`
**parent_loaded:** `True`

## Gate 0 protocol

{
  "evaluate_only_learn": "lumina_core/birth/awakening_grind.py:93",
  "parent_sha_const": "lumina_core/birth/awakening_entry_autopsy.py:38",
  "h_entry_neutral": "lumina_core/birth/awakening_entry_autopsy.py:186",
  "h_entry_flip": "lumina_core/birth/awakening_entry_autopsy.py:190",
  "h_missing_entry": "lumina_core/birth/awakening_entry_autopsy.py:173",
  "h_first_touch": "lumina_core/birth/awakening_entry_autopsy.py:194",
  "isolated_workspace": "lumina_core/birth/awakening_entry_autopsy.py:96",
  "forbidden_writes": "lumina_core/birth/awakening_entry_autopsy.py:70",
  "select_step_r": "lumina_core/birth/awakening_select_env.py:231",
  "close_ledger_row_keys": "lumina_core/birth/s5_close_ledger_trace.py:57",
  "sim_runner_open_stash": "lumina_core/birth/sim_runner.py:26",
  "run_evaluate_only_call": "lumina_core/birth/awakening_entry_autopsy_run.py:114",
  "gitpython_pin": "requirements-core.txt:140",
  "missing_sites": [],
  "gate0_complete": true
}

## Leg A (seed 20260902) — disk re-read

{
  "t0": {
    "n_all": 217,
    "n_policy": 150,
    "n_plant": 67,
    "wr_policy": 0.37333333333333335,
    "mean_r_policy": -0.16280700616093724,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "aff3cb1e3a6f5014",
    "optimizer_steps": 0
  },
  "t1": {
    "hole": {
      "n": 76,
      "wr": 0.0,
      "mean_r": -1.0520731660642308,
      "mean_usd": -118.70721003287197,
      "n_entry_neutral": 70,
      "n_entry_trend": 6,
      "n_entry_unknown": 0,
      "frac_entry_neutral": 0.9210526315789473,
      "frac_entry_trend": 0.07894736842105263,
      "frac_regime_flip": 0.07894736842105263,
      "median_bars_held": 13.5,
      "p25_bars_held": 5.0,
      "p75_bars_held": 30.5,
      "median_mae_r": -8.901336301037603,
      "median_mfe_r": 7.699734803615165,
      "bars_held_missing": false,
      "mae_r_missing": false
    },
    "target": {
      "n": 37,
      "wr": 1.0,
      "mean_r": 1.2124502971133304,
      "mean_usd": 146.56439591775714,
      "n_entry_neutral": 29,
      "n_entry_trend": 8,
      "n_entry_unknown": 0,
      "frac_entry_neutral": 0.7837837837837838,
      "frac_entry_trend": 0.21621621621621623,
      "frac_regime_flip": 0.16216216216216217,
      "median_bars_held": 13.0,
      "p25_bars_held": 8.0,
      "p75_bars_held": 19.0,
      "median_mae_r": -5.657869614688463,
      "median_mfe_r": 8.113122904982845,
      "bars_held_missing": false,
      "mae_r_missing": false
    }
  },
  "t2": {
    "min_n": 8.0,
    "trigger": {
      "NEUTRAL|stop": {
        "n": 74.0,
        "wr": 0.0,
        "sum_usd": -8787.239910314249,
        "mean_usd": -118.74648527451687,
        "mean_r": -1.0524616008843917,
        "cap_hit": 0.0,
        "stop": 74.0,
        "target": 0.0,
        "time_stop": 0.0,
        "target_clean": 0.0
      },
      "NEUTRAL|target": {
        "n": 29.0,
        "wr": 1.0,
        "sum_usd": 3964.9404553297363,
        "mean_usd": 136.72208466654263,
        "mean_r": 1.2122292193856428,
        "cap_hit": 0.0,
        "stop": 0.0,
        "target": 29.0,
        "time_stop": 0.0,
        "target_clean": 29.0
      },
      "NEUTRAL|time_stop": {
        "n": 19.0,
        "wr": 0.8421052631578947,
        "sum_usd": 2247.459321673738,
        "mean_usd": 118.28733271967042,
        "mean_r": 1.0465420165270218,
        "cap_hit": 1.0,
        "stop": 0.0,
        "target": 0.0,
        "time_stop": 19.0,
        "target_clean": 0.0
      },
      "TREND_DOWN|stop": {
        "n": 12.0,
        "wr": 0.0,
        "sum_usd": -1405.0119980412903,
        "mean_usd": -117.08433317010753,
        "mean_r": -1.0377580221504852,
        "cap_hit": 0.0,
        "stop": 12.0,
        "target": 0.0,
        "time_stop": 0.0,
        "target_clean": 0.0
      }
    },
    "small": {
      "TREND_DOWN|target": 3.0,
      "TREND_DOWN|time_stop": 1.0,
      "TREND_UP|stop": 5.0,
      "TREND_UP|target": 5.0,
      "TREND_UP|time_stop": 2.0
    }
  },
  "t3": {
    "n_hole": 76,
    "n_first_touch": 14,
    "share": 0.18421052631578946,
    "bars_held_missing": false
  },
  "flags": {
    "n_H": 76,
    "frac_neu": 0.9210526315789473,
    "frac_tr": 0.07894736842105263,
    "frac_ft": 0.18421052631578946,
    "missing_entry": 0.0,
    "missing_mae": 0.0,
    "H_MISSING_ENTRY": false,
    "H_ENTRY_NEUTRAL": true,
    "H_ENTRY_FLIP": false,
    "H_FIRST_TOUCH": false,
    "licensed_family": "OPEN_DECISION",
    "missing_fields": [],
    "gate1": "NONE"
  },
  "rows_n": 217
}

## Leg B (seed 20260903) — disk re-read

{
  "t0": {
    "n_all": 187,
    "n_policy": 150,
    "n_plant": 37,
    "wr_policy": 0.34,
    "mean_r_policy": -0.24524752185084342,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "e51ce9b724515e2e",
    "optimizer_steps": 0
  },
  "t1": {
    "hole": {
      "n": 82,
      "wr": 0.0,
      "mean_r": -1.0770073952838481,
      "mean_usd": -89.01498215982033,
      "n_entry_neutral": 73,
      "n_entry_trend": 9,
      "n_entry_unknown": 0,
      "frac_entry_neutral": 0.8902439024390244,
      "frac_entry_trend": 0.10975609756097561,
      "frac_regime_flip": 0.10975609756097561,
      "median_bars_held": 9.5,
      "p25_bars_held": 5.0,
      "p75_bars_held": 20.25,
      "median_mae_r": -7.597623779527693,
      "median_mfe_r": 6.17551471387498,
      "bars_held_missing": false,
      "mae_r_missing": false
    },
    "target": {
      "n": 32,
      "wr": 1.0,
      "mean_r": 1.198415054238808,
      "mean_usd": 98.96792678116854,
      "n_entry_neutral": 26,
      "n_entry_trend": 6,
      "n_entry_unknown": 0,
      "frac_entry_neutral": 0.8125,
      "frac_entry_trend": 0.1875,
      "frac_regime_flip": 0.21875,
      "median_bars_held": 16.5,
      "p25_bars_held": 6.0,
      "p75_bars_held": 27.0,
      "median_mae_r": -6.366735751482457,
      "median_mfe_r": 8.047322199876096,
      "bars_held_missing": false,
      "mae_r_missing": false
    }
  },
  "t2": {
    "min_n": 8.0,
    "trigger": {
      "NEUTRAL|stop": {
        "n": 82.0,
        "wr": 0.0,
        "sum_usd": -7299.648143662438,
        "mean_usd": -89.02009931295656,
        "mean_r": -1.077004217018419,
        "cap_hit": 0.0,
        "stop": 82.0,
        "target": 0.0,
        "time_stop": 0.0,
        "target_clean": 0.0
      },
      "NEUTRAL|target": {
        "n": 26.0,
        "wr": 1.0,
        "sum_usd": 2573.9271704267867,
        "mean_usd": 98.99719886256872,
        "mean_r": 1.1984297013457985,
        "cap_hit": 0.0,
        "stop": 0.0,
        "target": 26.0,
        "time_stop": 0.0,
        "target_clean": 26.0
      },
      "NEUTRAL|time_stop": {
        "n": 21.0,
        "wr": 0.8095238095238095,
        "sum_usd": 2096.3819282386476,
        "mean_usd": 99.82771086850703,
        "mean_r": 1.23584298772516,
        "cap_hit": 1.0,
        "stop": 0.0,
        "target": 0.0,
        "time_stop": 21.0,
        "target_clean": 0.0
      },
      "TREND_DOWN|stop": {
        "n": 10.0,
        "wr": 0.0,
        "sum_usd": -868.7466303399902,
        "mean_usd": -86.87466303399903,
        "mean_r": -1.051564796014674,
        "cap_hit": 0.0,
        "stop": 10.0,
        "target": 0.0,
        "time_stop": 0.0,
        "target_clean": 0.0
      }
    },
    "small": {
      "TREND_DOWN|target": 5.0,
      "TREND_DOWN|time_stop": 1.0,
      "TREND_UP|stop": 3.0,
      "TREND_UP|target": 1.0,
      "TREND_UP|time_stop": 1.0
    }
  },
  "t3": {
    "n_hole": 82,
    "n_first_touch": 14,
    "share": 0.17073170731707318,
    "bars_held_missing": false
  },
  "flags": {
    "n_H": 82,
    "frac_neu": 0.8902439024390244,
    "frac_tr": 0.10975609756097561,
    "frac_ft": 0.17073170731707318,
    "missing_entry": 0.0,
    "missing_mae": 0.0,
    "H_MISSING_ENTRY": false,
    "H_ENTRY_NEUTRAL": true,
    "H_ENTRY_FLIP": false,
    "H_FIRST_TOUCH": false,
    "licensed_family": "OPEN_DECISION",
    "missing_fields": [],
    "gate1": "NONE"
  },
  "rows_n": 187
}

## T4 existing-book close-only contrast (read-only)

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
  }
}

## Gate 1 law

NONE. No open-mask. No extra tax. No NEUTRAL drop. No time-stop rewrite.
Licensed future family string: `OPEN_DECISION` — not shipped as a controller.

