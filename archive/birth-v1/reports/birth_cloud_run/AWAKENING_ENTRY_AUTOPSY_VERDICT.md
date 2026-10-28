# AWAKENING ENTRY AUTOPSY VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN ENTRY_HOLE_AUTOPSY ENTRY_MEASURE_ONLY`
**Date:** 2026-09-03T12:01:42.706157+00:00
**Evaluated zip sha256:** `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
**optimizer_steps:** `0`
**H_MISSING_ENTRY A/B:** `False` / `False`
**H_ENTRY_NEUTRAL A/B:** `True` / `True`
**H_ENTRY_FLIP A/B:** `False` / `False`
**H_FIRST_TOUCH A/B:** `False` / `False`
**Licensed future family:** `OPEN_DECISION`
**Evolution Proof stamped:** `False`
**REAL:** `no`

### T0 — book identity

| Leg | n_all | n_policy | n_plant | wr_policy | mean_r_policy | zip sha16 | ticks_sha16 | price_sha16 | optimizer_steps |
|-----|-------|----------|---------|-----------|---------------|-----------|-------------|-------------|-----------------|
| A | 217 | 150 | 67 | 0.37333333333333335 | -0.16280700616093724 | 8cc435c68a37b0a0 | 7e86c2bb1c71d514 | aff3cb1e3a6f5014 | 0 |
| B | 187 | 150 | 37 | 0.34 | -0.24524752185084342 | 8cc435c68a37b0a0 | 7e86c2bb1c71d514 | e51ce9b724515e2e | 0 |

### T1 — hole cell vs contrast (policy-only)

- A hole (stop×NEUTRAL): `n=76 wr=0.0 mean_r=-1.0520731660642308 mean_usd=-118.70721003287197 entry_NEUTRAL=70 entry_TREND=6 entry_UNKNOWN=0 frac_neu=0.9210526315789473 frac_tr=0.07894736842105263 frac_flip=0.07894736842105263 median_held=13.5 p25=5.0 p75=30.5 median_mae_r=-8.901336301037603 median_mfe_r=7.699734803615165`
- A target: `n=37 wr=1.0 mean_r=1.2124502971133304 mean_usd=146.56439591775714 entry_NEUTRAL=29 entry_TREND=8 entry_UNKNOWN=0 frac_neu=0.7837837837837838 frac_tr=0.21621621621621623 frac_flip=0.16216216216216217 median_held=13.0 p25=8.0 p75=19.0 median_mae_r=-5.657869614688463 median_mfe_r=8.113122904982845`
- B hole (stop×NEUTRAL): `n=82 wr=0.0 mean_r=-1.0770073952838481 mean_usd=-89.01498215982033 entry_NEUTRAL=73 entry_TREND=9 entry_UNKNOWN=0 frac_neu=0.8902439024390244 frac_tr=0.10975609756097561 frac_flip=0.10975609756097561 median_held=9.5 p25=5.0 p75=20.25 median_mae_r=-7.597623779527693 median_mfe_r=6.17551471387498`
- B target: `n=32 wr=1.0 mean_r=1.198415054238808 mean_usd=98.96792678116854 entry_NEUTRAL=26 entry_TREND=6 entry_UNKNOWN=0 frac_neu=0.8125 frac_tr=0.1875 frac_flip=0.21875 median_held=16.5 p25=6.0 p75=27.0 median_mae_r=-6.366735751482457 median_mfe_r=8.047322199876096`

### T2 — entry_regime × close_reason (policy-only)

- A trigger cells: `{"NEUTRAL|stop": {"n": 74.0, "wr": 0.0, "sum_usd": -8787.239910314249, "mean_usd": -118.74648527451687, "mean_r": -1.0524616008843917, "cap_hit": 0.0, "stop": 74.0, "target": 0.0, "time_stop": 0.0, "target_clean": 0.0}, "NEUTRAL|target": {"n": 29.0, "wr": 1.0, "sum_usd": 3964.9404553297363, "mean_usd": 136.72208466654263, "mean_r": 1.2122292193856428, "cap_hit": 0.0, "stop": 0.0, "target": 29.0, "time_stop": 0.0, "target_clean": 29.0}, "NEUTRAL|time_stop": {"n": 19.0, "wr": 0.8421052631578947, "sum_usd": 2247.459321673738, "mean_usd": 118.28733271967042, "mean_r": 1.0465420165270218, "cap_hit": 1.0, "stop": 0.0, "target": 0.0, "time_stop": 19.0, "target_clean": 0.0}, "TREND_DOWN|stop": {"n": 12.0, "wr": 0.0, "sum_usd": -1405.0119980412903, "mean_usd": -117.08433317010753, "mean_r": -1.0377580221504852, "cap_hit": 0.0, "stop": 12.0, "target": 0.0, "time_stop": 0.0, "target_clean": 0.0}}`
- A small: `{'TREND_DOWN|target': 3.0, 'TREND_DOWN|time_stop': 1.0, 'TREND_UP|stop': 5.0, 'TREND_UP|target': 5.0, 'TREND_UP|time_stop': 2.0}`
- B trigger cells: `{"NEUTRAL|stop": {"n": 82.0, "wr": 0.0, "sum_usd": -7299.648143662438, "mean_usd": -89.02009931295656, "mean_r": -1.077004217018419, "cap_hit": 0.0, "stop": 82.0, "target": 0.0, "time_stop": 0.0, "target_clean": 0.0}, "NEUTRAL|target": {"n": 26.0, "wr": 1.0, "sum_usd": 2573.9271704267867, "mean_usd": 98.99719886256872, "mean_r": 1.1984297013457985, "cap_hit": 0.0, "stop": 0.0, "target": 26.0, "time_stop": 0.0, "target_clean": 26.0}, "NEUTRAL|time_stop": {"n": 21.0, "wr": 0.8095238095238095, "sum_usd": 2096.3819282386476, "mean_usd": 99.82771086850703, "mean_r": 1.23584298772516, "cap_hit": 1.0, "stop": 0.0, "target": 0.0, "time_stop": 21.0, "target_clean": 0.0}, "TREND_DOWN|stop": {"n": 10.0, "wr": 0.0, "sum_usd": -868.7466303399902, "mean_usd": -86.87466303399903, "mean_r": -1.051564796014674, "cap_hit": 0.0, "stop": 10.0, "target": 0.0, "time_stop": 0.0, "target_clean": 0.0}}`
- B small: `{'TREND_DOWN|target': 5.0, 'TREND_DOWN|time_stop': 1.0, 'TREND_UP|stop': 3.0, 'TREND_UP|target': 1.0, 'TREND_UP|time_stop': 1.0}`

### T3 — first-touch vs bleed on the hole

- A: `{'n_hole': 76, 'n_first_touch': 14, 'share': 0.18421052631578946, 'bars_held_missing': False}`
- B: `{'n_hole': 82, 'n_first_touch': 14, 'share': 0.17073170731707318, 'bars_held_missing': False}`

### T4 — existing-book close-only contrast (read-only)

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

### Honesty

Hole entries are already NEUTRAL. Next ticket may tax or refuse the open, not the close. Exam still grades NEUTRAL.

Playground does not open. No second learn(). Gate 1 law: NONE.

