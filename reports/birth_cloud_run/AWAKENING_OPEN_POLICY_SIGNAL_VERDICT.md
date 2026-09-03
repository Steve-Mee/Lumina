# AWAKENING OPEN POLICY SIGNAL VERDICT

**Overall:** `GRIND_REGRESS_AWAKENING_OPEN OPEN_POLICY_SIGNAL_AUTOPSY OPEN_MEASURE_ONLY`
**Date:** 2026-09-03T16:10:46.688259+00:00
**Evaluated zip sha256:** `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
**optimizer_steps:** `0`
**S_MISSING_U A/B:** `True` / `True`
**S_THIN A/B:** `True` / `True`
**Winning P A/B:** `none` / `none`
**Tag:** `S_MISSING`
**Licensed next family:** `OPEN_DECISION`
**Gate 1 law:** `NONE`
**Evolution Proof stamped:** `False`
**REAL:** `no`

### T0 — book identity

| Leg | n_all | n_policy | n_plant | wr_policy | mean_r_policy | zip sha16 | ticks_sha16 | price_sha16 | optimizer_steps |
|-----|-------|----------|---------|-----------|---------------|-----------|-------------|-------------|-----------------|
| A | 0 | 0 | 0 | 0.0 | 0.0 | 8cc435c68a37b0a0 |  |  | 0 |
| B | 0 | 0 | 0 | 0.0 | 0.0 | 8cc435c68a37b0a0 |  |  | 0 |

### T1 — universe U / H / W

- A U: `n=0 wr=0.0 mean_r=0.0 mean_usd=0.0` n_U=0 share_H=0.0 share_W=0.0
- A H: `n=0 wr=0.0 mean_r=0.0 mean_usd=0.0`
- A W: `n=0 wr=0.0 mean_r=0.0 mean_usd=0.0`
- B U: `n=0 wr=0.0 mean_r=0.0 mean_usd=0.0` n_U=0 share_H=0.0 share_W=0.0
- B H: `n=0 wr=0.0 mean_r=0.0 mean_usd=0.0`
- B W: `n=0 wr=0.0 mean_r=0.0 mean_usd=0.0`

### T2 — policy candidate grid

#### Leg A

| P | threshold | n_defined | missing_share | cov_H | cov_W | lift | S_SPLIT | S_HARM | missing |
|---|-----------|-----------|---------------|-------|-------|------|---------|--------|---------|
| `P_VALUE` | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | False | False |
| `P_ENTROPY` | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | False | False |
| `P_ACTION_MARGIN` | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | False | False |

#### Leg B

| P | threshold | n_defined | missing_share | cov_H | cov_W | lift | S_SPLIT | S_HARM | missing |
|---|-----------|-----------|---------------|-------|-------|------|---------|--------|---------|
| `P_VALUE` | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | False | False |
| `P_ENTROPY` | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | False | False |
| `P_ACTION_MARGIN` | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | False | False | False |

### T3 — paper counterfactual

- A: `{'P_VALUE': {'drop_H': 0.0, 'drop_W': 0.0, 'remaining_H': 0.0, 'remaining_W': 0.0}, 'P_ENTROPY': {'drop_H': 0.0, 'drop_W': 0.0, 'remaining_H': 0.0, 'remaining_W': 0.0}, 'P_ACTION_MARGIN': {'drop_H': 0.0, 'drop_W': 0.0, 'remaining_H': 0.0, 'remaining_W': 0.0}}`
- B: `{'P_VALUE': {'drop_H': 0.0, 'drop_W': 0.0, 'remaining_H': 0.0, 'remaining_W': 0.0}, 'P_ENTROPY': {'drop_H': 0.0, 'drop_W': 0.0, 'remaining_H': 0.0, 'remaining_W': 0.0}, 'P_ACTION_MARGIN': {'drop_H': 0.0, 'drop_W': 0.0, 'remaining_H': 0.0, 'remaining_W': 0.0}}`

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

### Honesty

No train law licensed.

Playground does not open. No learn(). Gate 1 law: NONE.

