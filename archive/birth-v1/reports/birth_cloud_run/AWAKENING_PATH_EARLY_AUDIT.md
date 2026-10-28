# AWAKENING PATH EARLY AUDIT

## Mission

Among policy trades that OPEN in NEUTRAL and are still open at locked bar k, does a path signal knowable at bar k (not at close, not the full-trade MAE) separate eventual hole H from eventual winners W?
Measure-only. Gate 1 law NONE. No PATH_EXIT. No learn().
**Date:** 2026-09-03T18:17:56.761695+00:00
**Gate 0 (PR #24 land):** `9a98853f08909c39205da647aa749a485c66c0a1`
**parent_loaded:** `True`

## Prior closed science (do not reopen)

- PR #22 ENTRY: hole already NEUTRAL at OPEN. Family OPEN_DECISION (closed as controller).
- PR #23 OPEN_SPLIT: five external open bits → S_NONE. Licensed H_NONE.
- PR #24 OPEN_POLICY_SIGNAL: value + entropy at OPEN → S_NONE. Licensed H_NONE.
- This ticket: locked-k path bits among still-open trades.

## Frozen hashes (parent / control / hole-tax) + bytes

| Role | sha256 | bytes |
|------|--------|-------|
| PARENT / Birth-exit π* | `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` | 202268 |
| CONTROL / PR #20 child | `db7daf3b978fe80624608e27111627b5b9c3070e71118c66673df996123dd029` | 202271 |
| HOLE-TAX child | `ca2ae0e5fa6f0e54215fe6c833e2ebff608b5e99426a6e75ff5f7167d6bb0325` | 202271 |

## Gate 0 protocol dump (inspect_path_early_protocol)

{
  "evaluate_only_learn": "lumina_core/birth/awakening_grind.py:104",
  "parent_sha_const": "lumina_core/birth/awakening_path_early.py:43",
  "k_locked": "lumina_core/birth/awakening_path_early_flags.py:34",
  "p_k3_mae_deep": "lumina_core/birth/awakening_path_early_flags.py:36",
  "p_k3_unreal_red": "lumina_core/birth/awakening_path_early_flags.py:37",
  "p_k5_mae_deep": "lumina_core/birth/awakening_path_early_flags.py:38",
  "p_k5_unreal_red": "lumina_core/birth/awakening_path_early_flags.py:39",
  "s_split": "lumina_core/birth/awakening_path_early_flags.py:85",
  "s_missing_path": "lumina_core/birth/awakening_path_early_flags.py:72",
  "licensed_next_family_h_none": "lumina_core/birth/awakening_path_early_flags.py:57",
  "license_never_open_decision": "lumina_core/birth/awakening_path_early_flags.py:ok",
  "isolated_workspace": "lumina_core/birth/awakening_path_early.py:94",
  "forbidden_writes": "lumina_core/birth/awakening_path_early.py:62",
  "forbidden_policy_signal_jsonl": "lumina_core/birth/awakening_path_early.py:84",
  "forbidden_open_split_jsonl": "lumina_core/birth/awakening_path_early.py:82",
  "close_ledger_path_k3_mae_r": "lumina_core/birth/s5_close_ledger_trace.py:82",
  "close_ledger_path_k3_mfe_r": "lumina_core/birth/s5_close_ledger_trace.py:83",
  "close_ledger_path_k3_unreal_r": "lumina_core/birth/s5_close_ledger_trace.py:84",
  "close_ledger_path_k5_mae_r": "lumina_core/birth/s5_close_ledger_trace.py:85",
  "close_ledger_path_k5_mfe_r": "lumina_core/birth/s5_close_ledger_trace.py:86",
  "close_ledger_path_k5_unreal_r": "lumina_core/birth/s5_close_ledger_trace.py:87",
  "snapshot_site": "lumina_core/birth/sim_runner_entry_telem.py:60",
  "run_evaluate_only_call": "lumina_core/birth/awakening_path_early_run.py:122",
  "gitpython_pin": "requirements-core.txt:140",
  "codecov_patch_50": "codecov.yml:16",
  "live_path_stash_attr_paths": {
    "path_k3_mae_r": "snapshot_path_at_k mae_usd / intended_risk at bars_from_entry==3",
    "path_k3_mfe_r": "snapshot_path_at_k mfe_usd / intended_risk at bars_from_entry==3",
    "path_k3_unreal_r": "mark-to-close unreal_usd / intended_risk at bars_from_entry==3",
    "path_k5_mae_r": "snapshot_path_at_k mae_usd / intended_risk at bars_from_entry==5",
    "path_k5_mfe_r": "snapshot_path_at_k mfe_usd / intended_risk at bars_from_entry==5",
    "path_k5_unreal_r": "mark-to-close unreal_usd / intended_risk at bars_from_entry==5"
  },
  "missing_sites": [],
  "gate0_complete": true
}

## Snapshot sites

snapshot function: `lumina_core/birth/sim_runner_entry_telem.py:60`
| key | extraction path |
|-----|-----------------|
| `path_k3_mae_r` | `snapshot_path_at_k mae_usd / intended_risk at bars_from_entry==3` |
| `path_k3_mfe_r` | `snapshot_path_at_k mfe_usd / intended_risk at bars_from_entry==3` |
| `path_k3_unreal_r` | `mark-to-close unreal_usd / intended_risk at bars_from_entry==3` |
| `path_k5_mae_r` | `snapshot_path_at_k mae_usd / intended_risk at bars_from_entry==5` |
| `path_k5_mfe_r` | `snapshot_path_at_k mfe_usd / intended_risk at bars_from_entry==5` |
| `path_k5_unreal_r` | `mark-to-close unreal_usd / intended_risk at bars_from_entry==5` |

## Fixture reuse (A/B ticks_sha16, price_sha16, reused_manifest)

- A ticks_sha16=`7e86c2bb1c71d514` price_sha16=`aff3cb1e3a6f5014` reused_manifest=`False`
- B ticks_sha16=`7e86c2bb1c71d514` price_sha16=`e51ce9b724515e2e` reused_manifest=`False`

## Evaluate-only call (run_evaluate_only kwargs, optimizer_steps)

call site: `lumina_core/birth/awakening_path_early_run.py:122`
runtime=`select_runtime()`, ledger_source=`awakening_path_early`, exploration_steps=0 (via s5_envelope_kwargs), TRAIN=False.
**optimizer_steps:** `0` (A t0=0 B t0=0)

## T0 identity + wire-vs-POLICY_SIGNAL-A

{
  "A": {
    "n_all": 201,
    "n_policy": 150,
    "n_plant": 51,
    "wr_policy": 0.30666666666666664,
    "mean_r_policy": -0.3092697822118258,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "aff3cb1e3a6f5014",
    "optimizer_steps": 0,
    "skip_replay": false
  },
  "B": {
    "n_all": 185,
    "n_policy": 150,
    "n_plant": 35,
    "wr_policy": 0.36,
    "mean_r_policy": -0.17973357939421974,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "7e86c2bb1c71d514",
    "price_sha16": "e51ce9b724515e2e",
    "optimizer_steps": 0,
    "skip_replay": false
  }
}

Wire vs POLICY_SIGNAL A: wr_policy baseline 0.293 n_policy 150. AND-stop fires only if both deltas exceed 0.03 / 15.

## T1 U / H / W plus per-k U_k

{
  "A": {
    "U": {
      "n": 126,
      "wr": 0.30952380952380953,
      "mean_r": -0.31054606719821454,
      "mean_usd": -36.00767898497853
    },
    "H": {
      "n": 78,
      "wr": 0.0,
      "mean_r": -1.0375115459769815,
      "mean_usd": -118.58056960747712
    },
    "W": {
      "n": 39,
      "wr": 1.0,
      "mean_r": 1.2679547632855288,
      "mean_usd": 142.97137460362268
    },
    "n_U": 126,
    "n_H": 78,
    "n_W": 39,
    "share_H": 0.6190476190476191,
    "share_W": 0.30952380952380953,
    "k": {
      "3": {
        "n_Uk": 117,
        "n_Hk": 71,
        "n_Wk": 37,
        "n_died_before_k": 9,
        "n_still_open": 117,
        "missing_share": 0.0,
        "S_THIN": false,
        "medians": {
          "mae_r": -3.51259620336855,
          "unreal_r": -0.04787176712367987
        }
      },
      "5": {
        "n_Uk": 106,
        "n_Hk": 61,
        "n_Wk": 36,
        "n_died_before_k": 20,
        "n_still_open": 106,
        "missing_share": 0.0,
        "S_THIN": false,
        "medians": {
          "mae_r": -3.8296067476950557,
          "unreal_r": 0.005016593011945927
        }
      }
    }
  },
  "B": {
    "U": {
      "n": 130,
      "wr": 0.3230769230769231,
      "mean_r": -0.30212686822107543,
      "mean_usd": -24.65668298935179
    },
    "H": {
      "n": 83,
      "wr": 0.0,
      "mean_r": -1.0515276607883177,
      "mean_usd": -86.93413944521618
    },
    "W": {
      "n": 42,
      "wr": 1.0,
      "mean_r": 1.2600750691100193,
      "mean_usd": 105.17692054743267
    },
    "n_U": 130,
    "n_H": 83,
    "n_W": 42,
    "share_H": 0.6384615384615384,
    "share_W": 0.3230769230769231,
    "k": {
      "3": {
        "n_Uk": 126,
        "n_Hk": 79,
        "n_Wk": 42,
        "n_died_before_k": 4,
        "n_still_open": 126,
        "missing_share": 0.0,
        "S_THIN": false,
        "medians": {
          "mae_r": -3.9487375469566715,
          "unreal_r": -0.16345737392751075
        }
      },
      "5": {
        "n_Uk": 113,
        "n_Hk": 68,
        "n_Wk": 41,
        "n_died_before_k": 17,
        "n_still_open": 113,
        "missing_share": 0.0,
        "S_THIN": false,
        "medians": {
          "mae_r": -4.343443747771533,
          "unreal_r": -0.08968917266227554
        }
      }
    }
  }
}

## T1b path-key distributions (null mean when n_defined=0)

{
  "A": {
    "path_k3_mae_r": {
      "U_k": {
        "n_defined": 117,
        "missing_share": 0.0,
        "mean": -4.185561323800151,
        "median": -3.51259620336855,
        "p25": -4.974736400816818,
        "p75": -2.359952902837377
      },
      "H_k": {
        "n_defined": 71,
        "missing_share": 0.0,
        "mean": -4.385404249019789,
        "median": -3.591248601483319,
        "p25": -4.966139413942366,
        "p75": -2.525173088648359
      },
      "W_k": {
        "n_defined": 37,
        "missing_share": 0.0,
        "mean": -3.7275267743632114,
        "median": -3.4071474646317235,
        "p25": -4.311073038823585,
        "p75": -2.359952902837377
      }
    },
    "path_k3_mfe_r": {
      "U_k": {
        "n_defined": 117,
        "missing_share": 0.0,
        "mean": 3.9295266818393784,
        "median": 3.360007210078354,
        "p25": 2.050386332028152,
        "p75": 4.970483868688241
      },
      "H_k": {
        "n_defined": 71,
        "missing_share": 0.0,
        "mean": 4.000289360813409,
        "median": 3.400607483034874,
        "p25": 2.030716420294624,
        "p75": 4.950468669931221
      },
      "W_k": {
        "n_defined": 37,
        "missing_share": 0.0,
        "mean": 3.738770537277544,
        "median": 3.216867227968669,
        "p25": 2.1645329155696045,
        "p75": 4.8644471081349945
      }
    },
    "path_k3_unreal_r": {
      "U_k": {
        "n_defined": 117,
        "missing_share": 0.0,
        "mean": -0.07086253858413177,
        "median": -0.04787176712367987,
        "p25": -0.31207468258373644,
        "p75": 0.21071412728591682
      },
      "H_k": {
        "n_defined": 71,
        "missing_share": 0.0,
        "mean": -0.23836543904703308,
        "median": -0.18419060866998557,
        "p25": -0.47603321271521104,
        "p75": 0.03552530421935103
      },
      "W_k": {
        "n_defined": 37,
        "missing_share": 0.0,
        "mean": 0.22755568287635025,
        "median": 0.21038514690483426,
        "p25": -0.07824630726251584,
        "p75": 0.5503417279111131
      }
    },
    "path_k5_mae_r": {
      "U_k": {
        "n_defined": 106,
        "missing_share": 0.0,
        "mean": -4.34850216604684,
        "median": -3.8296067476950557,
        "p25": -5.085806589834076,
        "p75": -2.6626342692986875
      },
      "H_k": {
        "n_defined": 61,
        "missing_share": 0.0,
        "mean": -4.400458383203998,
        "median": -3.933418699784047,
        "p25": -4.974736400816818,
        "p75": -2.810644651436997
      },
      "W_k": {
        "n_defined": 36,
        "missing_share": 0.0,
        "mean": -4.089749248155936,
        "median": -3.531814307223716,
        "p25": -5.267175992077644,
        "p75": -2.3608380511412483
      }
    },
    "path_k5_mfe_r": {
      "U_k": {
        "n_defined": 106,
        "missing_share": 0.0,
        "mean": 4.247402733431692,
        "median": 3.4260109637370944,
        "p25": 2.310160320060924,
        "p75": 5.586615780156863
      },
      "H_k": {
        "n_defined": 61,
        "missing_share": 0.0,
        "mean": 4.080368231554717,
        "median": 3.4266299533265956,
        "p25": 2.2492506931159477,
        "p75": 5.2304930554679645
      },
      "W_k": {
        "n_defined": 36,
        "missing_share": 0.0,
        "mean": 4.472762362048618,
        "median": 3.5350339344042494,
        "p25": 2.6727423513634716,
        "p75": 6.617134674052285
      }
    },
    "path_k5_unreal_r": {
      "U_k": {
        "n_defined": 106,
        "missing_share": 0.0,
        "mean": 0.03341253463296957,
        "median": 0.005016593011945927,
        "p25": -0.44335448790092463,
        "p75": 0.45890490961227864
      },
      "H_k": {
        "n_defined": 61,
        "missing_share": 0.0,
        "mean": -0.17563729031879552,
        "median": -0.11895644515764682,
        "p25": -0.6276928582895298,
        "p75": 0.19937242388047927
      },
      "W_k": {
        "n_defined": 36,
        "missing_share": 0.0,
        "mean": 0.4485597039804723,
        "median": 0.4154429426166345,
        "p25": 0.022159182186266453,
        "p75": 0.7538282923510832
      }
    }
  },
  "B": {
    "path_k3_mae_r": {
      "U_k": {
        "n_defined": 126,
        "missing_share": 0.0,
        "mean": -4.408286383859277,
        "median": -3.9487375469566715,
        "p25": -5.232164388184794,
        "p75": -2.7421604065449947
      },
      "H_k": {
        "n_defined": 79,
        "missing_share": 0.0,
        "mean": -4.628539852532187,
        "median": -4.238239946249123,
        "p25": -5.406823209487424,
        "p75": -2.950969564609062
      },
      "W_k": {
        "n_defined": 42,
        "missing_share": 0.0,
        "mean": -4.20298697653415,
        "median": -3.9819752235163883,
        "p25": -5.076484077605397,
        "p75": -2.741334056317414
      }
    },
    "path_k3_mfe_r": {
      "U_k": {
        "n_defined": 126,
        "missing_share": 0.0,
        "mean": 4.193315202611224,
        "median": 3.6253383600235347,
        "p25": 2.53877791840341,
        "p75": 4.89800493482965
      },
      "H_k": {
        "n_defined": 79,
        "missing_share": 0.0,
        "mean": 4.306022052076254,
        "median": 3.7143212787463966,
        "p25": 2.756369648985726,
        "p75": 4.972159219728471
      },
      "W_k": {
        "n_defined": 42,
        "missing_share": 0.0,
        "mean": 4.219788498550957,
        "median": 3.6987534914897138,
        "p25": 2.662685888148962,
        "p75": 4.859105858562203
      }
    },
    "path_k3_unreal_r": {
      "U_k": {
        "n_defined": 126,
        "missing_share": 0.0,
        "mean": -0.11718348657854155,
        "median": -0.16345737392751075,
        "p25": -0.5295412779070666,
        "p75": 0.23319748785010716
      },
      "H_k": {
        "n_defined": 79,
        "missing_share": 0.0,
        "mean": -0.2439244933823194,
        "median": -0.2833026298332683,
        "p25": -0.6049824052875418,
        "p75": 0.08273509836549735
      },
      "W_k": {
        "n_defined": 42,
        "missing_share": 0.0,
        "mean": 0.14755948506277128,
        "median": 0.10326145298098188,
        "p25": -0.1600047437648599,
        "p75": 0.46851417368506865
      }
    },
    "path_k5_mae_r": {
      "U_k": {
        "n_defined": 113,
        "missing_share": 0.0,
        "mean": -5.3283024854098535,
        "median": -4.343443747771533,
        "p25": -6.349265656260658,
        "p75": -3.203031805291869
      },
      "H_k": {
        "n_defined": 68,
        "missing_share": 0.0,
        "mean": -5.674018109241211,
        "median": -4.584488046783287,
        "p25": -7.288095868929481,
        "p75": -3.3532204039638946
      },
      "W_k": {
        "n_defined": 41,
        "missing_share": 0.0,
        "mean": -4.8038474878652995,
        "median": -4.116369917947191,
        "p25": -5.574865631658086,
        "p75": -3.1762883930289654
      }
    },
    "path_k5_mfe_r": {
      "U_k": {
        "n_defined": 113,
        "missing_share": 0.0,
        "mean": 5.234396153185912,
        "median": 4.048649452049881,
        "p25": 2.874531382089467,
        "p75": 6.547137600884987
      },
      "H_k": {
        "n_defined": 68,
        "missing_share": 0.0,
        "mean": 5.252100161041888,
        "median": 4.218063409162911,
        "p25": 3.134106136302071,
        "p75": 6.593132003608584
      },
      "W_k": {
        "n_defined": 41,
        "missing_share": 0.0,
        "mean": 5.2817966685981235,
        "median": 3.891659944715255,
        "p25": 2.8226810564113936,
        "p75": 6.124007581017326
      }
    },
    "path_k5_unreal_r": {
      "U_k": {
        "n_defined": 113,
        "missing_share": 0.0,
        "mean": -0.02243781839496228,
        "median": -0.08968917266227554,
        "p25": -0.4532143666553907,
        "p75": 0.3087410495279073
      },
      "H_k": {
        "n_defined": 68,
        "missing_share": 0.0,
        "mean": -0.28534466974939393,
        "median": -0.29881790309137746,
        "p25": -0.6745261466674898,
        "p75": 0.11055039025124017
      },
      "W_k": {
        "n_defined": 41,
        "missing_share": 0.0,
        "mean": 0.4345168354415983,
        "median": 0.24859484321669148,
        "p25": -0.029999074039608012,
        "p75": 0.5743076967752454
      }
    }
  }
}

## Paper-wick honesty

path_k3_mae_r paper median H=-3.591248601483319 W=-3.4071474646317235 (orders past −1 R on both). Costume risk; candidate not dropped. path_k5_mae_r paper median H=-3.933418699784047 W=-3.531814307223716 (orders past −1 R on both). Costume risk; candidate not dropped.

## T2 path candidate grid

{
  "A": {
    "P_K3_MAE_DEEP": {
      "threshold": -3.51259620336855,
      "n_defined": 117,
      "missing_share": 0.0,
      "cov_H": 0.5070422535211268,
      "cov_W": 0.4594594594594595,
      "lift": 0.047582794061667266,
      "S_SPLIT": false,
      "S_HARM": false,
      "S_THIN": false,
      "missing": false
    },
    "P_K3_UNREAL_RED": {
      "threshold": -0.04787176712367987,
      "n_defined": 117,
      "missing_share": 0.0,
      "cov_H": 0.6056338028169014,
      "cov_W": 0.32432432432432434,
      "lift": 0.28130947849257704,
      "S_SPLIT": true,
      "S_HARM": false,
      "S_THIN": false,
      "missing": false
    },
    "P_K5_MAE_DEEP": {
      "threshold": -3.8296067476950557,
      "n_defined": 106,
      "missing_share": 0.0,
      "cov_H": 0.5409836065573771,
      "cov_W": 0.4166666666666667,
      "lift": 0.12431693989071041,
      "S_SPLIT": false,
      "S_HARM": false,
      "S_THIN": false,
      "missing": false
    },
    "P_K5_UNREAL_RED": {
      "threshold": 0.005016593011945927,
      "n_defined": 106,
      "missing_share": 0.0,
      "cov_H": 0.6229508196721312,
      "cov_W": 0.2222222222222222,
      "lift": 0.40072859744990896,
      "S_SPLIT": true,
      "S_HARM": false,
      "S_THIN": false,
      "missing": false
    }
  },
  "B": {
    "P_K3_MAE_DEEP": {
      "threshold": -3.9487375469566715,
      "n_defined": 126,
      "missing_share": 0.0,
      "cov_H": 0.5189873417721519,
      "cov_W": 0.5238095238095238,
      "lift": -0.004822182037371947,
      "S_SPLIT": false,
      "S_HARM": false,
      "S_THIN": false,
      "missing": false
    },
    "P_K3_UNREAL_RED": {
      "threshold": -0.16345737392751075,
      "n_defined": 126,
      "missing_share": 0.0,
      "cov_H": 0.6329113924050633,
      "cov_W": 0.23809523809523808,
      "lift": 0.39481615430982525,
      "S_SPLIT": true,
      "S_HARM": false,
      "S_THIN": false,
      "missing": false
    },
    "P_K5_MAE_DEEP": {
      "threshold": -4.343443747771533,
      "n_defined": 113,
      "missing_share": 0.0,
      "cov_H": 0.5588235294117647,
      "cov_W": 0.43902439024390244,
      "lift": 0.11979913916786228,
      "S_SPLIT": false,
      "S_HARM": false,
      "S_THIN": false,
      "missing": false
    },
    "P_K5_UNREAL_RED": {
      "threshold": -0.08968917266227554,
      "n_defined": 113,
      "missing_share": 0.0,
      "cov_H": 0.6617647058823529,
      "cov_W": 0.24390243902439024,
      "lift": 0.4178622668579627,
      "S_SPLIT": true,
      "S_HARM": false,
      "S_THIN": false,
      "missing": false
    }
  }
}

## T3 paper counterfactual

{
  "A": {
    "P_K3_MAE_DEEP": {
      "drop_H": 36.0,
      "drop_W": 17.0,
      "remaining_H": 35.0,
      "remaining_W": 20.0
    },
    "P_K3_UNREAL_RED": {
      "drop_H": 43.0,
      "drop_W": 12.0,
      "remaining_H": 28.0,
      "remaining_W": 25.0
    },
    "P_K5_MAE_DEEP": {
      "drop_H": 33.0,
      "drop_W": 15.0,
      "remaining_H": 28.0,
      "remaining_W": 21.0
    },
    "P_K5_UNREAL_RED": {
      "drop_H": 38.0,
      "drop_W": 8.0,
      "remaining_H": 23.0,
      "remaining_W": 28.0
    }
  },
  "B": {
    "P_K3_MAE_DEEP": {
      "drop_H": 41.0,
      "drop_W": 22.0,
      "remaining_H": 38.0,
      "remaining_W": 20.0
    },
    "P_K3_UNREAL_RED": {
      "drop_H": 50.0,
      "drop_W": 10.0,
      "remaining_H": 29.0,
      "remaining_W": 32.0
    },
    "P_K5_MAE_DEEP": {
      "drop_H": 38.0,
      "drop_W": 18.0,
      "remaining_H": 30.0,
      "remaining_W": 23.0
    },
    "P_K5_UNREAL_RED": {
      "drop_H": 45.0,
      "drop_W": 10.0,
      "remaining_H": 23.0,
      "remaining_W": 31.0
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
  }
}

## T5 opposite-tail (READ_ONLY_FLIP, cannot win)

{
  "A": {
    "P_K3_MAE_DEEP": {
      "cov_H": 0.49295774647887325,
      "cov_W": 0.5405405405405406,
      "lift": -0.04758279406166732,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    },
    "P_K3_UNREAL_RED": {
      "cov_H": 0.39436619718309857,
      "cov_W": 0.6756756756756757,
      "lift": -0.2813094784925771,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    },
    "P_K5_MAE_DEEP": {
      "cov_H": 0.45901639344262296,
      "cov_W": 0.5833333333333334,
      "lift": -0.12431693989071041,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    },
    "P_K5_UNREAL_RED": {
      "cov_H": 0.3770491803278688,
      "cov_W": 0.7777777777777778,
      "lift": -0.40072859744990896,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    }
  },
  "B": {
    "P_K3_MAE_DEEP": {
      "cov_H": 0.4810126582278481,
      "cov_W": 0.47619047619047616,
      "lift": 0.004822182037371947,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    },
    "P_K3_UNREAL_RED": {
      "cov_H": 0.3670886075949367,
      "cov_W": 0.7619047619047619,
      "lift": -0.39481615430982514,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    },
    "P_K5_MAE_DEEP": {
      "cov_H": 0.4411764705882353,
      "cov_W": 0.5609756097560976,
      "lift": -0.11979913916786233,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    },
    "P_K5_UNREAL_RED": {
      "cov_H": 0.3382352941176471,
      "cov_W": 0.7560975609756098,
      "lift": -0.4178622668579627,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    }
  }
}

## Licensing decision (A SSOT)

**Tag:** `S_MULTI`  **Winning P:** `none`  **Licensed next family:** `H_NONE`  **Gate 1 law:** `NONE`
Open-time market bits S_NONE (PR #23). Open-time π* internals S_NONE (PR #24).
This ticket asked whether locked-k path bits separate H from W among still-open trades.
Replay: skip_replay=false. n_U A/B = 126/130.  U_3 / U_5 A = 117 / 106.
Winning tag: S_MULTI.
Licensed next family: H_NONE.
Law shipped: NONE.
Playground: no.
Evolution Proof stamped: False.
REAL: no.

## Forbidden-path grep (learn, training_reward, PATH_EXIT controller)

{
  "hygiene_token_in_birth": [],
  "model_learn_in_birth": [
    "lumina_core/birth/awakening_hole_tax_path.py",
    "lumina_core/birth/awakening_hole_tax_run.py",
    "lumina_core/birth/awakening_open_policy_signal_report.py",
    "lumina_core/birth/awakening_open_split_report.py",
    "lumina_core/birth/awakening_path_early_report.py",
    "lumina_core/birth/awakening_select_path.py",
    "lumina_core/birth/awakening_select_run.py"
  ],
  "path_exit_controller": false
}

## Capital / autonomy / experiment

- **Capital:** SIM only. No flatten-at-k. Close-time MAE is not a k-feature.
- **Autonomy:** frozen π* unchanged; the organism measures whether early path separates hole from winners among trades still open at locked k.
- **Experiment:** one variable (locked-k path split). Open-time families stay closed. Playground stays closed. Representation rebuild is the next ticket only if S_NONE.

