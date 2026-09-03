# AWAKENING_PATH_UNREAL_K3_AUDIT

## Gate 0
- origin/main SHA `5079d66af8dfd74933989bac459e97d3fbb0daca`
- PR #25 merge SHA `5079d66af8dfd74933989bac459e97d3fbb0daca`
- worker-test touched: no
- parent_loaded: `True`
- date: `2026-09-03T20:30:44.704341+00:00`

## Source
- path_early A/B sha256 `4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb` / `0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356`
- missing_share k=3 A `0.0`
- path chosen: rescore
- parent zip sha256 `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
- skip_replay `false` replay_ran `false`

## Protocol inspect

{
  "k_locked": "lumina_core/birth/awakening_path_unreal_k3_flags.py:42",
  "candidate_names_only_k3_unreal": "lumina_core/birth/awakening_path_unreal_k3_flags.py:43",
  "pred_unreal_red": "lumina_core/birth/awakening_path_unreal_k3_flags.py:37",
  "universe_k_reuse": "lumina_core/birth/awakening_path_unreal_k3_flags.py:39",
  "still_open_at_k_reuse": "lumina_core/birth/awakening_path_unreal_k3_flags.py:38",
  "flag_s_split": "lumina_core/birth/awakening_path_unreal_k3_flags.py:29",
  "split_lift_import": "lumina_core/birth/awakening_path_unreal_k3_flags.py:10",
  "license_path_exit_p_k3_unreal_red": "lumina_core/birth/awakening_path_unreal_k3_flags.py:45",
  "h_none_on_miss_none": "lumina_core/birth/awakening_path_unreal_k3_flags.py:156",
  "forbidden_write_path_early_jsonl": "lumina_core/birth/awakening_path_unreal_k3.py:39",
  "evaluate_only_learn": "lumina_core/birth/awakening_grind.py:104",
  "parent_sha_const": "lumina_core/birth/awakening_path_unreal_k3.py:32",
  "overall_inconclusive_branch": "lumina_core/birth/awakening_path_unreal_k3.py:281",
  "gitpython_pin": "requirements-core.txt:140",
  "codecov_patch_50": "codecov.yml:16",
  "missing_sites": [],
  "gate0_complete": true
}

## Flags

{
  "source": "path_early_jsonl",
  "source_A_sha256": "4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb",
  "source_B_sha256": "0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356",
  "skip_replay": false,
  "replay_ran": false,
  "A": {
    "n_U": 126,
    "n_H": 78,
    "n_W": 39,
    "n_died_before_3": 9,
    "U_3": {
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
    "S_MISSING_U": false,
    "S_MISSING_PATH": false,
    "S_THIN": false,
    "winning_P": "P_K3_UNREAL_RED",
    "tag": "S_SPLIT",
    "candidates": {
      "P_K3_UNREAL_RED": {
        "threshold": -0.04787176712367987,
        "missing": false,
        "missing_share": 0.0,
        "n_defined": 117,
        "cov_H": 0.6056338028169014,
        "cov_W": 0.32432432432432434,
        "lift": 0.28130947849257704,
        "S_THIN": false,
        "S_SPLIT": true,
        "S_HARM": false,
        "drop_H": 43.0,
        "drop_W": 12.0,
        "remaining_H": 28.0,
        "remaining_W": 25.0,
        "READ_ONLY_FLIP": false
      }
    },
    "gate1": "NONE"
  },
  "B": {
    "n_U": 130,
    "n_H": 83,
    "n_W": 42,
    "n_died_before_3": 4,
    "U_3": {
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
    "S_MISSING_U": false,
    "S_MISSING_PATH": false,
    "S_THIN": false,
    "winning_P": "P_K3_UNREAL_RED",
    "tag": "S_SPLIT",
    "candidates": {
      "P_K3_UNREAL_RED": {
        "threshold": -0.16345737392751075,
        "missing": false,
        "missing_share": 0.0,
        "n_defined": 126,
        "cov_H": 0.6329113924050633,
        "cov_W": 0.23809523809523808,
        "lift": 0.39481615430982525,
        "S_THIN": false,
        "S_SPLIT": true,
        "S_HARM": false,
        "drop_H": 50.0,
        "drop_W": 10.0,
        "remaining_H": 29.0,
        "remaining_W": 32.0,
        "READ_ONLY_FLIP": false
      }
    },
    "gate1": "NONE"
  },
  "tag": "S_SPLIT",
  "winning_P": "P_K3_UNREAL_RED",
  "licensed_next_family": "PATH_EXIT:P_K3_UNREAL_RED",
  "gate1": "NONE",
  "optimizer_steps": 0,
  "evaluated_zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
  "evolution_proof_stamped": false,
  "REAL": "no",
  "overall": "GRIND_REGRESS_AWAKENING_OPEN PATH_UNREAL_K3_AUTOPSY PATH_MEASURE_ONLY"
}

## Reproduction vs PATH_EARLY A P_K3_UNREAL_RED
- lift `0.28130947849257704` (locked `0.28130947849257704`)
- cov_H `0.6056338028169014` (locked `0.6056338028169014`)
- cov_W `0.32432432432432434` (locked `0.32432432432432434`)
- n_Uk3 `117` (locked 117)

## Honesty

PATH_EARLY S_MULTI because P_K3_UNREAL_RED and P_K5_UNREAL_RED both split. Paper MAE did not.
This ticket locks k=3 a priori and candidate set size 1: P_K3_UNREAL_RED.
k=5 is not a candidate.
Source: path_early_jsonl. skip_replay=false. replay_ran=false.
n_U A/B = 126/130  U_3 A/B = 117/126
Winning tag: S_SPLIT.
Licensed next family: PATH_EXIT:P_K3_UNREAL_RED.
Law shipped: NONE.
Flatten-at-3 shipped: no.
Playground: no.
Evolution Proof stamped: False.
REAL: no.

- law NONE, flatten no, Playground no, Proof false

## T0 / T1 / T1b / T2 / T3 / T4 / T5

{
  "A": {
    "source": "path_early_jsonl",
    "source_A_sha256": "4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb",
    "source_B_sha256": "0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356",
    "n_all": 201,
    "n_policy": 150,
    "n_plant": 51,
    "wr_policy": 0.30666666666666664,
    "mean_r_policy": -0.3092697822118258,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "",
    "price_sha16": "",
    "optimizer_steps": 0,
    "skip_replay": false,
    "replay_ran": false
  },
  "B": {
    "source": "path_early_jsonl",
    "source_A_sha256": "4604b5082d9ab13e1fdabdfcc9577728117be7183a0accf69f8d599c7050d0eb",
    "source_B_sha256": "0a349eb2ab48e8f8194d177c8b4dee760ef2010647a9d2c8548292d953dc1356",
    "n_all": 185,
    "n_policy": 150,
    "n_plant": 35,
    "wr_policy": 0.36,
    "mean_r_policy": -0.17973357939421974,
    "zip_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
    "ticks_sha16": "",
    "price_sha16": "",
    "optimizer_steps": 0,
    "skip_replay": false,
    "replay_ran": false
  }
}
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
    "n_Uk3": 117,
    "n_Hk3": 71,
    "n_Wk3": 37,
    "n_died_before_3": 9,
    "share_H": 0.6190476190476191,
    "share_W": 0.30952380952380953,
    "U_3": {
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
    "n_Uk3": 126,
    "n_Hk3": 79,
    "n_Wk3": 42,
    "n_died_before_3": 4,
    "share_H": 0.6384615384615384,
    "share_W": 0.3230769230769231,
    "U_3": {
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
    }
  }
}
{
  "A": {
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
      },
      "contrast_only": false
    },
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
      },
      "contrast_only": true
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
      },
      "contrast_only": true
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
      },
      "contrast_only": true
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
      },
      "contrast_only": true
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
      },
      "contrast_only": true
    }
  },
  "B": {
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
      },
      "contrast_only": false
    },
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
      },
      "contrast_only": true
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
      },
      "contrast_only": true
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
      },
      "contrast_only": true
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
      },
      "contrast_only": true
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
      },
      "contrast_only": true
    }
  }
}
{
  "A": {
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
    }
  },
  "B": {
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
    }
  }
}
{
  "A": {
    "P_K3_UNREAL_RED": {
      "drop_H": 43.0,
      "drop_W": 12.0,
      "remaining_H": 28.0,
      "remaining_W": 25.0
    }
  },
  "B": {
    "P_K3_UNREAL_RED": {
      "drop_H": 50.0,
      "drop_W": 10.0,
      "remaining_H": 29.0,
      "remaining_W": 32.0
    }
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
  }
}
{
  "A": {
    "P_K3_UNREAL_RED": {
      "cov_H": 0.39436619718309857,
      "cov_W": 0.6756756756756757,
      "lift": -0.2813094784925771,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    }
  },
  "B": {
    "P_K3_UNREAL_RED": {
      "cov_H": 0.3670886075949367,
      "cov_W": 0.7619047619047619,
      "lift": -0.39481615430982514,
      "READ_ONLY_FLIP": true,
      "S_SPLIT": false
    }
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
    "lumina_core/birth/awakening_path_unreal_k3_report.py",
    "lumina_core/birth/awakening_select_path.py",
    "lumina_core/birth/awakening_select_run.py"
  ],
  "flatten_at_3": false,
  "playground": false
}

