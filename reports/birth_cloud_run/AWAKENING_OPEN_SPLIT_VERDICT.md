# AWAKENING OPEN SPLIT VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN OPEN_SPLIT_AUTOPSY OPEN_MEASURE_ONLY`
**Date:** 2026-09-03T14:08:57.985341+00:00
**Evaluated zip sha256:** `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
**optimizer_steps:** `0`
**S_MISSING_U A/B:** `False` / `False`
**S_THIN A/B:** `False` / `False`
**Winning F A/B:** `none` / `none`
**Tag:** `S_NONE`
**Licensed next family:** `H_NONE`
**Gate 1 law:** `NONE`
**Evolution Proof stamped:** `False`
**REAL:** `no`

### T0 — book identity

| Leg | n_all | n_policy | n_plant | wr_policy | mean_r_policy | zip sha16 | ticks_sha16 | price_sha16 | optimizer_steps |
|-----|-------|----------|---------|-----------|---------------|-----------|-------------|-------------|-----------------|
| A | 199 | 150 | 49 | 0.34 | -0.21940697972311662 | 8cc435c68a37b0a0 | 7e86c2bb1c71d514 | aff3cb1e3a6f5014 | 0 |
| B | 176 | 150 | 26 | 0.36 | -0.19267549262352934 | 8cc435c68a37b0a0 | 7e86c2bb1c71d514 | e51ce9b724515e2e | 0 |

### T1 — universe U / H / W

- A U: `n=131 wr=0.3511450381679389 mean_r=-0.19657087391052563 mean_usd=-22.232998573942467` n_U=131 share_H=0.5648854961832062 share_W=0.3511450381679389
- A H: `n=74 wr=0.0 mean_r=-1.0377556132059704 mean_usd=-117.09102836517542`
- A W: `n=46 wr=1.0 mean_r=1.2974970662698004 mean_usd=146.2381929439049`
- B U: `n=134 wr=0.3358208955223881 mean_r=-0.23592537334649266 mean_usd=-19.545688424836836` n_U=134 share_H=0.5895522388059702 share_W=0.3358208955223881
- B H: `n=79 wr=0.0 mean_r=-1.0515305000514765 mean_usd=-86.92960115809905`
- B W: `n=45 wr=1.0 mean_r=1.3032196960437301 mean_usd=107.60615972393703`

### T2 — candidate grid

#### Leg A

| F | n_defined | missing_share | cov_H | cov_W | lift | S_SPLIT | S_HARM | missing |
|---|-----------|---------------|-------|-------|------|---------|--------|---------|
| `F_OCC_FLOOR` | 131 | 0.0 | 0.918918918918919 | 0.9130434782608695 | 0.005875440658049458 | False | False | False |
| `F_SESSION_EARLY` | 131 | 0.0 | 0.0 | 0.0 | 0.0 | False | False | False |
| `F_TIGHT_RANGE` | 131 | 0.0 | 0.1891891891891892 | 0.2608695652173913 | -0.0716803760282021 | False | False | False |
| `F_AFTER_STOP` | 129 | 0.01526717557251911 | 0.32432432432432434 | 0.391304347826087 | -0.06698002350176263 | False | False | False |
| `F_IMBAL_FLAT` | 131 | 0.0 | 0.0 | 0.0 | 0.0 | False | False | False |

#### Leg B

| F | n_defined | missing_share | cov_H | cov_W | lift | S_SPLIT | S_HARM | missing |
|---|-----------|---------------|-------|-------|------|---------|--------|---------|
| `F_OCC_FLOOR` | 134 | 0.0 | 0.9620253164556962 | 0.9777777777777777 | -0.015752461322081523 | False | False | False |
| `F_SESSION_EARLY` | 134 | 0.0 | 0.0 | 0.0 | 0.0 | False | False | False |
| `F_TIGHT_RANGE` | 134 | 0.0 | 0.22784810126582278 | 0.17777777777777778 | 0.05007032348804499 | False | False | False |
| `F_AFTER_STOP` | 133 | 0.007462686567164201 | 0.4050632911392405 | 0.5333333333333333 | -0.12827004219409283 | False | True | False |
| `F_IMBAL_FLAT` | 134 | 0.0 | 0.0 | 0.0 | 0.0 | False | False | False |

### T3 — paper counterfactual

- A: `{'F_OCC_FLOOR': {'drop_H': 68.0, 'drop_W': 42.0, 'remaining_H': 6.0, 'remaining_W': 4.0}, 'F_SESSION_EARLY': {'drop_H': 0.0, 'drop_W': 0.0, 'remaining_H': 74.0, 'remaining_W': 46.0}, 'F_TIGHT_RANGE': {'drop_H': 14.0, 'drop_W': 12.0, 'remaining_H': 60.0, 'remaining_W': 34.0}, 'F_AFTER_STOP': {'drop_H': 24.0, 'drop_W': 18.0, 'remaining_H': 50.0, 'remaining_W': 28.0}, 'F_IMBAL_FLAT': {'drop_H': 0.0, 'drop_W': 0.0, 'remaining_H': 74.0, 'remaining_W': 46.0}}`
- B: `{'F_OCC_FLOOR': {'drop_H': 76.0, 'drop_W': 44.0, 'remaining_H': 3.0, 'remaining_W': 1.0}, 'F_SESSION_EARLY': {'drop_H': 0.0, 'drop_W': 0.0, 'remaining_H': 79.0, 'remaining_W': 45.0}, 'F_TIGHT_RANGE': {'drop_H': 18.0, 'drop_W': 8.0, 'remaining_H': 61.0, 'remaining_W': 37.0}, 'F_AFTER_STOP': {'drop_H': 32.0, 'drop_W': 24.0, 'remaining_H': 47.0, 'remaining_W': 21.0}, 'F_IMBAL_FLAT': {'drop_H': 0.0, 'drop_W': 0.0, 'remaining_H': 79.0, 'remaining_W': 45.0}}`

### T4 — read-only contrast (policy hole n / mean_r)

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

### Honesty

NEUTRAL-open hole and NEUTRAL-open winners are not separable with the locked candidate set. Blanket refuse remains forbidden.

Playground does not open. No learn(). Gate 1 law: NONE.

