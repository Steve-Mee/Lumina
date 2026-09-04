# GENESIS_HOLD_COMPARE_AUDIT

## Gate 0 live-check

```json
{
  "origin_main": "da01d6d9f202d6da914cf377c29b0b776f359389",
  "POLICY_EDGE_MIN_TRADES": 150,
  "OBSERVATION_DIM": 43,
  "pct_synthetic": 0.0,
  "pct_real": 100.0,
  "pct_REAL_NT": 100.0,
  "G5_flags_present": true,
  "G5_tag": "GENESIS_EYES_FAIL",
  "fixture_train_hash": "5726ae7e83ff3d48",
  "REAL": "no"
}
```

## T0 identity

```json
{
  "origin_main": "da01d6d9f202d6da914cf377c29b0b776f359389",
  "genesis_train_hash": "5726ae7e83ff3d48",
  "newborn_sha16": "d313b107e99e03a5",
  "child_sha16": "a9ffa8529e02f2d8",
  "OBSERVATION_DIM": 43,
  "POLICY_EDGE_MIN_TRADES": 150
}
```

## T1 honesty

```json
{
  "pct_synthetic_cloud_fixture": 0.0,
  "pct_real": 100.0,
  "certificate_reasons_contain_synthetic_source": true,
  "synthetic_source_reasons": [
    "synthetic_source:synthetic_cloud_fixture"
  ],
  "min_real_data_pct": 95.0
}
```

## T2 hold compare

### Leg A

```json
{
  "leg": "A",
  "n_policy_birth": 150,
  "n_policy_child": 113,
  "bars_held_p50_birth": 15.5,
  "bars_held_p50_child": 90.0,
  "bars_held_p90_birth": 80.0,
  "bars_held_p90_child": 280.8,
  "trades_per_10k_birth": 69.49270326615705,
  "trades_per_10k_child": 52.35116979383832,
  "n_H_birth": 67,
  "n_H_child": 31,
  "mean_r_birth": -0.13306818214641977,
  "mean_r_child": -0.06581195881282897,
  "cause_tag": "HOLD_LONGER",
  "child_last_close_reason": "stop"
}
```

### Leg B

```json
{
  "leg": "B",
  "n_policy_birth": 150,
  "n_policy_child": 103,
  "bars_held_p50_birth": 9.0,
  "bars_held_p50_child": 90.0,
  "bars_held_p90_birth": 62.099999999999994,
  "bars_held_p90_child": 298.9999999999999,
  "trades_per_10k_birth": 69.49270326615705,
  "trades_per_10k_child": 47.71832290942784,
  "n_H_birth": 55,
  "n_H_child": 21,
  "mean_r_birth": -0.3946853762542806,
  "mean_r_child": -0.06422429818509125,
  "cause_tag": "HOLD_LONGER",
  "child_last_close_reason": "target"
}
```

## T3 license

```json
{
  "combined_tag": "GENESIS_FOLLOWON_OK",
  "gate1_tag": "HONEST_OK",
  "gate2_tag": "HOLD_LONGER",
  "law": "SHADOW",
  "licensed_next_family": "GENESIS_EYES_BUDGET",
  "Proof": false,
  "REAL": "no",
  "GENESIS_EYES_OK": false,
  "HOLE_MOVED_A": false,
  "HOLE_MOVED_B": false,
  "honesty": "PR #35 G5 is GENESIS_EYES_FAIL. This PR does not convert it to EYES_OK. Floor 150 is unchanged. No second 10k. Engine 100% on certified synthetic is a lie; Gate 1 removes that lie. Source synthetic_cloud_fixture. REAL=no. Playground=no. Proof=false."
}
```

## Honesty

PR #35 G5 is GENESIS_EYES_FAIL. This PR does not convert it to EYES_OK. Floor 150 is unchanged. No second 10k. Engine 100% on certified synthetic is a lie; Gate 1 removes that lie. Source synthetic_cloud_fixture. REAL=no. Playground=no. Proof=false.

PR #35 G5 remains GENESIS_EYES_FAIL. n_policy 113/103 restated. Floor 150 stays.
GENESIS_EYES_OK is forbidden. learn() was not called. REAL=no.

## flags

```json
{
  "source": "genesis_followon",
  "gate1_tag": "HONEST_OK",
  "gate2_tag": "HOLD_LONGER",
  "tag": "GENESIS_FOLLOWON_OK",
  "law": "SHADOW",
  "licensed_next_family": "GENESIS_EYES_BUDGET",
  "POLICY_EDGE_MIN_TRADES": 150,
  "n_policy_A_child": 113,
  "n_policy_B_child": 103,
  "HOLE_MOVED_A": false,
  "HOLE_MOVED_B": false,
  "GENESIS_EYES_OK": false,
  "learn_called": false,
  "optimizer_steps": 0,
  "evolution_proof_stamped": false,
  "REAL": "no",
  "playground": false,
  "hook_default": false,
  "used_old_path_early": false,
  "real_data_pct_synthetic_fixture": 0.0,
  "overall": "GENESIS_FOLLOWON SHADOW_MEASURE"
}
```
