# AWAKENING OPEN SPLIT AUDIT

## Mission

Among policy trades that OPEN in NEUTRAL, which feature knowable at the open bar separates `stop × close NEUTRAL` (hole H) from +R closes (winners W)?
Measure-only. Gate 1 law NONE. No open-mask. No learn().
**Date:** 2026-09-03T14:08:57.985341+00:00
**Gate 0 (PR #22 land):** `25061876cd5d249d18fd8e12e5890d965f10f8c7`
**parent_loaded:** `True`

## Frozen hashes (parent / control / hole-tax) + bytes

| Role | sha256 | bytes |
|------|--------|-------|
| PARENT / Birth-exit π* | `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` | 202268 |
| CONTROL / PR #20 child | `db7daf3b978fe80624608e27111627b5b9c3070e71118c66673df996123dd029` | 202271 |
| HOLE-TAX child | `ca2ae0e5fa6f0e54215fe6c833e2ebff608b5e99426a6e75ff5f7167d6bb0325` | 202271 |

## Gate 0 protocol dump (inspect_open_split_protocol)

{
  "evaluate_only_learn": "lumina_core/birth/awakening_grind.py:93",
  "parent_sha_const": "lumina_core/birth/awakening_open_split.py:53",
  "f_occ_floor": "lumina_core/birth/awakening_open_split.py:19",
  "f_session_early": "lumina_core/birth/awakening_open_split.py:20",
  "f_tight_range": "lumina_core/birth/awakening_open_split.py:21",
  "f_after_stop": "lumina_core/birth/awakening_open_split.py:17",
  "f_imbal_flat": "lumina_core/birth/awakening_open_split.py:18",
  "occupancy_floor_neighborhood": "lumina_core/birth/awakening_open_split_flags.py:8",
  "s_split": "lumina_core/birth/awakening_open_split_flags.py:161",
  "s_harm": "lumina_core/birth/awakening_open_split_flags.py:179",
  "s_missing_u": "lumina_core/birth/awakening_open_split_flags.py:152",
  "isolated_workspace": "lumina_core/birth/awakening_open_split.py:100",
  "forbidden_writes": "lumina_core/birth/awakening_open_split.py:72",
  "select_step_r": "lumina_core/birth/awakening_select_env.py:231",
  "close_ledger_open_occ_flat": "lumina_core/birth/s5_close_ledger_trace.py:66",
  "close_ledger_open_cum_flat": "lumina_core/birth/s5_close_ledger_trace.py:67",
  "close_ledger_open_in_band_seen": "lumina_core/birth/s5_close_ledger_trace.py:68",
  "close_ledger_open_session_phase": "lumina_core/birth/s5_close_ledger_trace.py:69",
  "close_ledger_open_confluence": "lumina_core/birth/s5_close_ledger_trace.py:70",
  "close_ledger_open_news_proximity": "lumina_core/birth/s5_close_ledger_trace.py:71",
  "close_ledger_open_imbalance": "lumina_core/birth/s5_close_ledger_trace.py:72",
  "close_ledger_open_range_stop_frac": "lumina_core/birth/s5_close_ledger_trace.py:73",
  "close_ledger_open_side": "lumina_core/birth/s5_close_ledger_trace.py:74",
  "close_ledger_bars_since": "lumina_core/birth/s5_close_ledger_trace.py:75",
  "close_ledger_open_participation_mode": "lumina_core/birth/s5_close_ledger_trace.py:76",
  "start_open_telem_optional": "lumina_core/birth/sim_runner_entry_telem.py:218",
  "gather_open_features": "lumina_core/birth/sim_runner_entry_telem.py:84",
  "update_open_telem_gather": "lumina_core/birth/sim_runner_entry_telem.py:84",
  "stamp_open_host": "lumina_core/birth/sim_runner.py:629",
  "run_evaluate_only_call": "lumina_core/birth/awakening_open_split_run.py:111",
  "gitpython_pin": "requirements-core.txt:140",
  "codecov_patch_50": "codecov.yml:16",
  "live_stash_attr_paths": {
    "open_occ_flat": "host.occupancy_control_flat | info.get('occupancy_control_flat')",
    "open_cum_flat": "host.stage_range_flat_bars/stage_range_total_signals | host.range_flat_bars/range_total_signals",
    "open_in_band_seen": "host.occupancy_in_band_seen | info.get('occupancy_in_band_seen')",
    "open_session_phase": "tick['bible_session_phase'] if key present",
    "open_confluence": "tick['bible_confluence'] if key present",
    "open_news_proximity": "tick['bible_news_proximity'] if key present",
    "open_imbalance": "tick['imbalance'] iff key present and value is not None",
    "open_range_stop_frac": "(high-low)/entry / stop_pct via host.geometry.stop_pct | envelope.participation_stop_pct | info.stop_pct",
    "open_side": "stash.side from start_open_telem",
    "bars_since_prev_policy_stop": "entry_bar - host._last_policy_stop_bar (omit if none)",
    "open_participation_mode": "host.config.participation_mode | info.participation_mode | host.participation_mode"
  },
  "live_stash_gather_site": "lumina_core/birth/sim_runner_entry_telem.py:84",
  "missing_sites": [],
  "gate0_complete": true
}

## Live open-stash sites (file:line + attribute path per key)

gather_open_features: `lumina_core/birth/sim_runner_entry_telem.py:84`
stamp_open_host: `lumina_core/birth/sim_runner.py:629`
start_open_telem optional: `lumina_core/birth/sim_runner_entry_telem.py:218`

| key | attr path | A | B |
|-----|-----------|---|---|
| `open_occ_flat` | `host.occupancy_control_flat | info.get('occupancy_control_flat')` | produced | produced |
| `open_cum_flat` | `host.stage_range_flat_bars/stage_range_total_signals | host.range_flat_bars/range_total_signals` | produced | produced |
| `open_in_band_seen` | `host.occupancy_in_band_seen | info.get('occupancy_in_band_seen')` | produced | produced |
| `open_session_phase` | `tick['bible_session_phase'] if key present` | produced | produced |
| `open_confluence` | `tick['bible_confluence'] if key present` | produced | produced |
| `open_news_proximity` | `tick['bible_news_proximity'] if key present` | produced | produced |
| `open_imbalance` | `tick['imbalance'] iff key present and value is not None` | produced | produced |
| `open_range_stop_frac` | `(high-low)/entry / stop_pct via host.geometry.stop_pct | envelope.participation_stop_pct | info.stop_pct` | produced | produced |
| `open_side` | `stash.side from start_open_telem` | produced | produced |
| `bars_since_prev_policy_stop` | `entry_bar - host._last_policy_stop_bar (omit if none)` | produced | produced |
| `open_participation_mode` | `host.config.participation_mode | info.participation_mode | host.participation_mode` | produced | produced |

## Fixture reuse (A/B ticks_sha16, price_sha16, reused_manifest)

- A ticks_sha16=`7e86c2bb1c71d514` price_sha16=`aff3cb1e3a6f5014` reused_manifest=`True`
- B ticks_sha16=`7e86c2bb1c71d514` price_sha16=`e51ce9b724515e2e` reused_manifest=`False`

## Evaluate-only call (run_evaluate_only kwargs, optimizer_steps)

call site: `lumina_core/birth/awakening_open_split_run.py:111`
runtime=`select_runtime()`, ledger_source=`awakening_open_split`, exploration_steps=0 (via s5_envelope_kwargs), TRAIN=False.
**optimizer_steps:** `0` (A t0=0 B t0=0)

## T0 identity + wire-vs-autopsy-A

{
  "A": {
    "n_all": 199,
    "n_policy": 150,
    "n_plant": 49,
    "wr_policy": 0.34,
    "mean_r_policy": -0.21940697972311662,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "aff3cb1e3a6f5014",
    "optimizer_steps": 0
  },
  "B": {
    "n_all": 176,
    "n_policy": 150,
    "n_plant": 26,
    "wr_policy": 0.36,
    "mean_r_policy": -0.19267549262352934,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "e51ce9b724515e2e",
    "optimizer_steps": 0
  }
}

Wire vs PR #22 autopsy A: wr_policy baseline 0.373 n_policy 150. AND-stop fires only if both deltas exceed 0.03 / 15.

## T1 U / H / W

{
  "A": {
    "U": {
      "n": 131,
      "wr": 0.3511450381679389,
      "mean_r": -0.19657087391052563,
      "mean_usd": -22.232998573942467
    },
    "H": {
      "n": 74,
      "wr": 0.0,
      "mean_r": -1.0377556132059704,
      "mean_usd": -117.09102836517542
    },
    "W": {
      "n": 46,
      "wr": 1.0,
      "mean_r": 1.2974970662698004,
      "mean_usd": 146.2381929439049
    },
    "n_U": 131,
    "n_H": 74,
    "n_W": 46,
    "share_H": 0.5648854961832062,
    "share_W": 0.3511450381679389
  },
  "B": {
    "U": {
      "n": 134,
      "wr": 0.3358208955223881,
      "mean_r": -0.23592537334649266,
      "mean_usd": -19.545688424836836
    },
    "H": {
      "n": 79,
      "wr": 0.0,
      "mean_r": -1.0515305000514765,
      "mean_usd": -86.92960115809905
    },
    "W": {
      "n": 45,
      "wr": 1.0,
      "mean_r": 1.3032196960437301,
      "mean_usd": 107.60615972393703
    },
    "n_U": 134,
    "n_H": 79,
    "n_W": 45,
    "share_H": 0.5895522388059702,
    "share_W": 0.3358208955223881
  }
}

## T2 candidate grid

{
  "A": {
    "F_OCC_FLOOR": {
      "n_defined": 131,
      "missing_share": 0.0,
      "cov_H": 0.918918918918919,
      "cov_W": 0.9130434782608695,
      "lift": 0.005875440658049458,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "F_SESSION_EARLY": {
      "n_defined": 131,
      "missing_share": 0.0,
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "F_TIGHT_RANGE": {
      "n_defined": 131,
      "missing_share": 0.0,
      "cov_H": 0.1891891891891892,
      "cov_W": 0.2608695652173913,
      "lift": -0.0716803760282021,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "F_AFTER_STOP": {
      "n_defined": 129,
      "missing_share": 0.01526717557251911,
      "cov_H": 0.32432432432432434,
      "cov_W": 0.391304347826087,
      "lift": -0.06698002350176263,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "F_IMBAL_FLAT": {
      "n_defined": 131,
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
    "F_OCC_FLOOR": {
      "n_defined": 134,
      "missing_share": 0.0,
      "cov_H": 0.9620253164556962,
      "cov_W": 0.9777777777777777,
      "lift": -0.015752461322081523,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "F_SESSION_EARLY": {
      "n_defined": 134,
      "missing_share": 0.0,
      "cov_H": 0.0,
      "cov_W": 0.0,
      "lift": 0.0,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "F_TIGHT_RANGE": {
      "n_defined": 134,
      "missing_share": 0.0,
      "cov_H": 0.22784810126582278,
      "cov_W": 0.17777777777777778,
      "lift": 0.05007032348804499,
      "S_SPLIT": false,
      "S_HARM": false,
      "missing": false
    },
    "F_AFTER_STOP": {
      "n_defined": 133,
      "missing_share": 0.007462686567164201,
      "cov_H": 0.4050632911392405,
      "cov_W": 0.5333333333333333,
      "lift": -0.12827004219409283,
      "S_SPLIT": false,
      "S_HARM": true,
      "missing": false
    },
    "F_IMBAL_FLAT": {
      "n_defined": 134,
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
    "F_OCC_FLOOR": {
      "drop_H": 68.0,
      "drop_W": 42.0,
      "remaining_H": 6.0,
      "remaining_W": 4.0
    },
    "F_SESSION_EARLY": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 74.0,
      "remaining_W": 46.0
    },
    "F_TIGHT_RANGE": {
      "drop_H": 14.0,
      "drop_W": 12.0,
      "remaining_H": 60.0,
      "remaining_W": 34.0
    },
    "F_AFTER_STOP": {
      "drop_H": 24.0,
      "drop_W": 18.0,
      "remaining_H": 50.0,
      "remaining_W": 28.0
    },
    "F_IMBAL_FLAT": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 74.0,
      "remaining_W": 46.0
    }
  },
  "B": {
    "F_OCC_FLOOR": {
      "drop_H": 76.0,
      "drop_W": 44.0,
      "remaining_H": 3.0,
      "remaining_W": 1.0
    },
    "F_SESSION_EARLY": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 79.0,
      "remaining_W": 45.0
    },
    "F_TIGHT_RANGE": {
      "drop_H": 18.0,
      "drop_W": 8.0,
      "remaining_H": 61.0,
      "remaining_W": 37.0
    },
    "F_AFTER_STOP": {
      "drop_H": 32.0,
      "drop_W": 24.0,
      "remaining_H": 47.0,
      "remaining_W": 21.0
    },
    "F_IMBAL_FLAT": {
      "drop_H": 0.0,
      "drop_W": 0.0,
      "remaining_H": 79.0,
      "remaining_W": 45.0
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
  }
}

## Licensing decision (A SSOT)

**Tag:** `S_NONE`  **Winning F:** `none`  **Licensed next family:** `H_NONE`  **Gate 1 law:** `NONE`
NEUTRAL-open hole and NEUTRAL-open winners are not separable with the locked candidate set. Blanket refuse remains forbidden.

## Forbidden-path grep (learn, training_reward, OPEN_FILTER controller)

{
  "hygiene_token_in_birth": [],
  "model_learn_in_birth": [
    "lumina_core/birth/awakening_hole_tax_path.py",
    "lumina_core/birth/awakening_hole_tax_run.py",
    "lumina_core/birth/awakening_open_split_report.py",
    "lumina_core/birth/awakening_select_path.py",
    "lumina_core/birth/awakening_select_run.py"
  ],
  "open_filter_controller": false
}

## Capital / autonomy / experiment

- **Capital:** SIM only. Exam dollars stay the fill. No mask on live participation.
- **Autonomy:** measurement compounds; the organism learns whether NEUTRAL-open is one door or two.
- **Experiment:** one variable (at-OPEN split inside NEUTRAL-open). Close-tax family stays closed. Blanket NEUTRAL-refuse stays forbidden.

